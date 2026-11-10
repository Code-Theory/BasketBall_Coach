"""Local pretrained shooting analysis; no model training or network access."""
import math
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'data' / 'matplotlib'))
import cv2
import mediapipe as mp
import numpy as np
import onnxruntime as ort

POSE_MODEL = ROOT / 'models' / 'pose_landmarker_lite.task'
BALL_MODELS = {
    'standard': ('yolov8s.onnx', (32,)),
    'fast': ('yolov8n.onnx', (32,)),
    'swish': ('swish_basketball.onnx', (0, 2)),
}


def angle(a, b, c):
    v, w = np.asarray(a) - b, np.asarray(c) - b
    d = np.linalg.norm(v) * np.linalg.norm(w)
    return round(float(np.degrees(np.arccos(np.clip(np.dot(v, w) / d, -1, 1)))), 1) if d > 1e-6 else None


def point(landmarks, index, width, height):
    p = landmarks[index]
    if p.visibility < .5 or not (0 <= p.x <= 1 and 0 <= p.y <= 1):
        return None
    return np.array([p.x * width, p.y * height], dtype=float)


def metrics(points, width, height, ball, preferred_side=None):
    sides = []
    for side, ids in [('left', (11, 13, 15, 23, 25, 27)), ('right', (12, 14, 16, 24, 26, 28))]:
        shoulder, elbow, wrist, hip, knee, ankle = [point(points, i, width, height) for i in ids]
        el = angle(shoulder, elbow, wrist) if all(p is not None for p in (shoulder, elbow, wrist)) else None
        kn = angle(hip, knee, ankle) if all(p is not None for p in (hip, knee, ankle)) else None
        dist = float(np.linalg.norm(wrist - ball)) if wrist is not None and ball is not None else None
        wrist_high = bool(wrist[1] < shoulder[1]) if wrist is not None and shoulder is not None else None
        sides.append({'side': side, 'elbow': el, 'knee': kn, 'wrist': wrist, 'distance': dist, 'wrist_above_shoulder': wrist_high})
    visible = [s for s in sides if s['distance'] is not None]
    chosen = next((s for s in sides if s['side'] == preferred_side), None)
    if chosen is None:
        chosen = min(visible, key=lambda s: s['distance']) if visible else max(sides, key=lambda s: sum(s[k] is not None for k in ('elbow', 'knee')))
    return chosen


def annotate(frame, pose, ball, hoop):
    canvas = frame.copy()
    h, w = canvas.shape[:2]
    if pose:
        for a, b in [(11, 12), (11, 13), (13, 15), (12, 14), (14, 16), (11, 23),
                     (12, 24), (23, 24), (23, 25), (25, 27), (24, 26), (26, 28)]:
            p, q = point(pose, a, w, h), point(pose, b, w, h)
            if p is not None and q is not None:
                cv2.line(canvas, tuple(p.astype(int)), tuple(q.astype(int)), (114, 218, 192), 2, cv2.LINE_AA)
        for i in (11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28):
            p = point(pose, i, w, h)
            if p is not None:
                cv2.circle(canvas, tuple(p.astype(int)), 4, (33, 175, 255), -1, cv2.LINE_AA)
    if ball is not None:
        cv2.circle(canvas, tuple(np.asarray(ball, dtype=int)), 11, (51, 161, 255), 2, cv2.LINE_AA)
    if hoop:
        x1, y1, x2, y2 = hoop
        cv2.rectangle(canvas, (int(x1*w), int(y1*h)), (int(x2*w), int(y2*h)), (114, 218, 192), 2)
    return canvas


class BallDetector:
    def __init__(self):
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 2
        available = ort.get_available_providers()
        providers = (['CUDAExecutionProvider'] if 'CUDAExecutionProvider' in available else []) + ['CPUExecutionProvider']
        name = os.environ.get('COURTVISION_BALL_MODEL', 'swish').lower()
        if name not in BALL_MODELS:
            raise ValueError('COURTVISION_BALL_MODEL must be standard, fast, or swish')
        if name == 'swish' and not (ROOT / 'models' / BALL_MODELS['swish'][0]).is_file():
            if 'COURTVISION_BALL_MODEL' in os.environ:
                raise FileNotFoundError('Swish-Vision model is missing from models/swish_basketball.onnx')
            name = 'standard'
        filename, self.ball_classes = BALL_MODELS[name]
        self.model_name = name
        self.net = ort.InferenceSession(str(ROOT / 'models' / filename), sess_options=opts, providers=providers)
        self.provider = self.net.get_providers()[0]
        input_info = self.net.get_inputs()[0]
        self.input = input_info.name
        self.input_h, self.input_w = input_info.shape[2:]
        self.candidates = []

    def detect(self, frame, previous=None, gap_seconds=0):
        self.candidates = []
        h, w = frame.shape[:2]
        scale = min(self.input_w / w, self.input_h / h)
        rw, rh = int(w * scale), int(h * scale)
        left, top = (self.input_w-rw)//2, (self.input_h-rh)//2
        resized = cv2.resize(frame, (rw, rh))
        image = np.full((self.input_h, self.input_w, 3), 114, dtype=np.uint8)
        image[top:top+rh, left:left+rw] = resized
        blob = np.ascontiguousarray(image[:, :, ::-1].transpose(2, 0, 1)[None], dtype=np.float32) / 255
        output = self.net.run(None, {self.input: blob})[0][0].T
        # YOLOv8 output has 4 coordinates followed by class scores. Swish-Vision
        # labels both "basketball" and "sports ball"; never treat the rim as a ball.
        confidence = output[:, [4 + index for index in self.ball_classes]].max(axis=1)
        if not len(confidence):
            return None
        # Prefer a plausible continuation over an unrelated high-confidence ball.
        candidates = np.flatnonzero(confidence >= .20)
        if not len(candidates):
            return None
        centers = output[candidates, :2].copy()
        centers[:, 0] = (centers[:, 0] - left) / scale
        centers[:, 1] = (centers[:, 1] - top) / scale
        valid = ((centers[:, 0] >= 0) & (centers[:, 0] < w) &
                 (centers[:, 1] >= 0) & (centers[:, 1] < h))
        candidates, centers = candidates[valid], centers[valid]
        if not len(candidates):
            return None
        scores = confidence[candidates].copy()
        sizes = output[candidates, 2:4] / scale
        # The upstream tracker consumes multiple bounding boxes and confidences.
        boxes_xywh = [[float(x-bw/2), float(y-bh/2), float(bw), float(bh)]
                      for (x, y), (bw, bh) in zip(centers, sizes)]
        keep = cv2.dnn.NMSBoxes(boxes_xywh, scores.tolist(), .20, .45)
        for index in np.asarray(keep).reshape(-1):
            x, y, bw, bh = boxes_xywh[int(index)]
            if bw > 1 and bh > 1:
                self.candidates.append(((x, y, x+bw, y+bh), float(scores[int(index)])))
        if previous is not None:
            distance = np.linalg.norm(centers - previous, axis=1)
            # A short gap may cover rapid flight, but not a jump across the frame.
            limit = math.hypot(w, h) * min(.45, .12 + gap_seconds * 1.0)
            valid = distance <= limit
            if not np.any(valid):
                return None
            centers, scores, distance = centers[valid], scores[valid], distance[valid]
            scores = scores - .20 * distance / limit
        return centers[int(np.argmax(scores))].astype(float)



def analyze(path, output_dir, hoop, progress):
    from shot_logic import ShotRecognizer
    from hoop_tracker import HoopTracker
    from tracker_bridge import ShotTrackerBridge

    started = time.perf_counter()
    progress(1, 'Loading the ball and pose models')
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError('Could not open this video. Try an MP4 file.')
    fps = cap.get(cv2.CAP_PROP_FPS)
    if not math.isfinite(fps) or fps <= 0:
        fps = 30
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if width <= 0 or height <= 0:
        cap.release()
        raise ValueError('Could not determine the video dimensions.')
    # Preserve more of a fast ball's flight near the rim. For typical 24/30 fps
    # video this analyzes every frame; higher frame rates sample at >=24 fps.
    stride = max(1, int(fps / 24))
    detector = BallDetector()
    recognizer = ShotRecognizer(width, height, hoop)
    shot_tracker = ShotTrackerBridge(width, height)
    options = mp.tasks.vision.PoseLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(POSE_MODEL)),
        running_mode=mp.tasks.vision.RunningMode.VIDEO, num_poses=1,
        min_pose_detection_confidence=.5, min_pose_presence_confidence=.5)
    last_ball, last_frame = None, -1
    tracks, segment = [], []
    detected_balls = processed = 0
    hoop_tracker = None
    try:
        with mp.tasks.vision.PoseLandmarker.create_from_options(options) as landmarker:
            frame_number = -1
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                frame_number += 1
                if frame_number % stride:
                    continue
                seconds = frame_number / fps
                if hoop and hoop_tracker is None:
                    hoop_tracker = HoopTracker(frame, hoop)
                current_hoop = hoop_tracker.update(frame) if hoop_tracker else None
                gap = (frame_number-last_frame)/fps if last_frame >= 0 else 0
                ball = detector.detect(frame, last_ball if gap <= .35 else None, gap)
                if ball is not None:
                    detected_balls += 1
                    if gap > .35 and segment:
                        tracks.append(segment)
                        segment = []
                    segment.append(tuple(ball.astype(int)))
                    last_ball, last_frame = ball, frame_number
                image = mp.Image(image_format=mp.ImageFormat.SRGB,
                                 data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                pose_result = landmarker.detect_for_video(image, int(round(seconds * 1000)))
                pose = pose_result.pose_landmarks[0] if pose_result.pose_landmarks else None
                values = metrics(pose, width, height, ball) if pose else None
                side_values = {side: metrics(pose, width, height, ball, side) for side in ('left', 'right')} if pose else {}
                encoded = original_encoded = None
                if pose:
                    annotated = annotate(frame, pose, ball, current_hoop)
                    original = frame
                    if width > 960:
                        annotated = cv2.resize(annotated, (960, round(height * 960 / width)))
                        original = cv2.resize(frame, (960, round(height * 960 / width)))
                    ok_jpg, encoded = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    encoded = encoded.tobytes() if ok_jpg else None
                    ok_original, original_encoded = cv2.imencode('.jpg', original, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    original_encoded = original_encoded.tobytes() if ok_original else None
                in_hand = bool(values and values['distance'] is not None and values['distance'] < .08 * min(width, height))
                shot_tracker.step(seconds, detector.candidates, current_hoop, in_hand)
                recognizer.observe({'time': seconds, 'frame': frame_number,
                                    'ball': tuple(float(x) for x in ball) if ball is not None else None,
                                    'values': values, 'side_values': side_values, 'image': encoded, 'original': original_encoded, 'hoop': current_hoop})
                processed += 1
                if processed % 3 == 0:
                    progress(max(1, min(95, round(frame_number/max(total, 1)*95))), 'Tracking the ball and analyzing movement')
    finally:
        cap.release()
    progress(96, 'Preparing your shot review')
    if segment:
        tracks.append(segment)
    if tracks:
        background = np.full((height, width, 3), (28, 24, 22), dtype=np.uint8)
        for segment in tracks:
            if len(segment) > 1:
                cv2.polylines(background, [np.array(segment, dtype=np.int32)], False, (80, 157, 255), 3)
            for pt in segment:
                cv2.circle(background, pt, 3, (80, 157, 255), -1)
        if hoop:
            cv2.rectangle(background, (int(hoop[0]*width), int(hoop[1]*height)),
                          (int(hoop[2]*width), int(hoop[3]*height)), (114, 218, 192), 2)
        cv2.imwrite(str(output_dir / 'trajectory.jpg'), background)

    shots = []
    for index, raw in enumerate(recognizer.shots):
        stages = {}
        for name in ('load', 'release', 'follow'):
            obs = raw[name]
            if not obs:
                continue
            values = obs['side_values'].get(raw['side'])
            if not values:
                continue
            filename = 'shot_{}_{}.jpg'.format(index, name)
            if obs['image']:
                (output_dir / filename).write_bytes(obs['image'])
            original_name = 'shot_{}_{}_original.jpg'.format(index, name)
            if obs.get('original'):
                (output_dir / original_name).write_bytes(obs['original'])
            stages[name] = {'frame': obs['frame'], 'seconds': round(obs['time'], 2),
                            'elbow': values['elbow'], 'knee': values['knee'],
                            'wrist_above_shoulder': values['wrist_above_shoulder'],
                            'side': raw['side'], 'image': filename if obs['image'] else None,
                            'original_image': original_name if obs.get('original') else None}
        # Only the integrated tracker may classify a make or miss.
        outcome = 'uncertain'
        angle_value = recognizer.apparent_angle(raw)
        notes = []
        load, release = stages.get('load'), stages.get('release')
        if load and load['knee'] is not None:
            notes.append('Knee angle at the estimated load: {}\u00b0. Smaller angles indicate more bend in this camera view.'.format(load['knee']))
        if load and release and load['knee'] is not None and release['knee'] is not None:
            notes.append('Knee angle changed by {:+.1f}\u00b0 from load to release.'.format(release['knee']-load['knee']))
            if release['knee'] - load['knee'] < 10:
                notes.append('Review cue: little knee-angle change was visible between these frames. Watch whether your legs extend smoothly into the shot; camera angle can affect the measurement.')
            else:
                notes.append('Review cue: the visible knee straightened during the shot. Replay the load and release to check whether that extension feels coordinated with your arm.')
        if release and release['elbow'] is not None:
            notes.append('Elbow angle at the estimated release: {}\u00b0.'.format(release['elbow']))
        if release and release['wrist_above_shoulder'] is False:
            notes.append('Review cue: the tracked wrist appeared below the shoulder in the estimated release frame. Check whether the release frame and shooting side are correct.')
        follow = stages.get('follow')
        if follow and follow['elbow'] is not None:
            notes.append('Elbow angle after release: {}\u00b0. Review whether your shooting arm extends through the shot.'.format(follow['elbow']))
            if release and release['elbow'] is not None:
                notes.append('Review cue: compare the release and follow-through frames to see whether your shooting arm continues extending toward the basket.')
        if load and release and load['elbow'] is not None and release['elbow'] is not None:
            notes.append('Elbow angle changed by {:+.1f}\u00b0 from the load frame to release.'.format(release['elbow'] - load['elbow']))
        if angle_value is not None:
            notes.append('Apparent ball launch angle: {}\u00b0 in the image; camera perspective affects this estimate.'.format(angle_value))
        if not load or not release or not follow:
            notes.append('Some form stages were not visible enough to measure. Try a steady side view with your full body in frame.')
        if not notes:
            notes.append('Form could not be measured clearly for this attempt.')
        notes.append('These observations may help review the shot; they do not establish why it missed.')
        shots.append({'id': index, 'seconds': round(raw['time'], 2), 'outcome': outcome,
                      'stages': stages, 'apparent_angle': angle_value, 'notes': notes})
    shot_tracker.match(shots)
    counts = {name: sum(s['outcome'] == name for s in shots) for name in ('made', 'missed', 'uncertain')}
    return {'shots': shots, 'stages': shots[0]['stages'] if shots else {},
            'attempts': len(shots), 'makes': counts['made'], 'misses': counts['missed'],
            'uncertain_shots': counts['uncertain'], 'trajectory': 'trajectory.jpg' if tracks else None,
            'ball_frames': detected_balls, 'processed_frames': processed,
            'duration': round(time.perf_counter()-started, 1), 'video_duration': round(total/fps, 1),
            'provider': detector.provider, 'ball_model': detector.model_name, 'hoop_selected': bool(hoop),
            'notes': shots[0]['notes'] if shots else ['No clear release was detected. A shot may have been missed; try a closer, well-lit view.']}
