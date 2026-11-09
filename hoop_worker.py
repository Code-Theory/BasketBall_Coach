"""Detect a stationary rim with the bundled TensorFlow graph.

Runs under the bundled Windows Python 3.6 environment, separate from the main application.
Prints one JSON object; diagnostics go to stderr.
"""
import json
import os
import sys
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '2')
os.environ.setdefault('CUDA_VISIBLE_DEVICES', '-1')
import cv2
import numpy as np
import tensorflow.compat.v1 as tf

tf.disable_v2_behavior()
video_path, model_path = sys.argv[1:3]
graph = tf.Graph()
with graph.as_default():
    graph_def = tf.GraphDef()
    with tf.gfile.GFile(model_path, 'rb') as stream:
        graph_def.ParseFromString(stream.read())
    tf.import_graph_def(graph_def, name='')
image_input = graph.get_tensor_by_name('image_tensor:0')
outputs = [graph.get_tensor_by_name(name + ':0') for name in
           ('detection_boxes', 'detection_scores', 'detection_classes')]
cap = cv2.VideoCapture(video_path)
frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
indices = sorted(set([0, max(0, int(frame_count*.15)), max(0, int(frame_count*.35))]))
candidates = []
config = tf.ConfigProto(device_count={'GPU': 0}, intra_op_parallelism_threads=2, inter_op_parallelism_threads=2)
with tf.Session(graph=graph, config=config) as session:
    for index in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = cap.read()
        if not ok:
            continue
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        boxes, scores, classes = session.run(outputs, feed_dict={image_input: rgb[None]})
        choices = [(float(score), box) for box, score, label in zip(boxes[0], scores[0], classes[0])
                   if int(label) == 2 and score >= .45]
        if choices:
            score, box = max(choices, key=lambda item: item[0])
            y1, x1, y2, x2 = (float(v) for v in box)
            if 0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1 and x2-x1 >= .01 and y2-y1 >= .005:
                candidates.append({'box': [x1, y1, x2, y2], 'score': score})
cap.release()
# A stable detection across frames is preferred; accept an isolated strong one.
clusters = []
for candidate in candidates:
    b = candidate['box']
    group = []
    for other in candidates:
        c = other['box']
        if abs((b[0]+b[2]-c[0]-c[2])/2) <= max(b[2]-b[0], c[2]-c[0]) and abs((b[1]+b[3]-c[1]-c[3])/2) <= max(b[3]-b[1], c[3]-c[1]):
            group.append(other)
    clusters.append(group)
selected = max(clusters, key=lambda group: (len(group), sum(c['score'] for c in group))) if clusters else []
if selected and (len(selected) >= 2 or selected[0]['score'] >= .7):
    box = np.median([c['box'] for c in selected], axis=0).tolist()
    # The detector includes the hanging net; the opening lies at the top.
    box[3] = min(1.0, box[1] + max(.005, .4 * (box[3] - box[1])))
    print(json.dumps({'hoop': box, 'confidence': round(float(np.mean([c['score'] for c in selected])), 2), 'frames': len(selected)}))
else:
    print(json.dumps({'hoop': None, 'confidence': None, 'frames': len(selected)}))
