import os
import json
import math
import subprocess
import re
import shutil
import threading
import uuid
from pathlib import Path

import cv2
from flask import Flask, abort, jsonify, render_template, request, send_from_directory, send_file
from werkzeug.utils import secure_filename

from analysis import analyze

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
DATA.mkdir(exist_ok=True)
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024
jobs = {}
lock = threading.Lock()
processing = threading.Lock()
hoop_processing = threading.Lock()
HOOP_PYTHON = ROOT / 'runtime' / 'hoop-python36' / 'python.exe'
HOOP_GRAPH = ROOT / 'models' / 'hoop_detector.pb'


def write_json(path, data):
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    os.replace(temporary, path)


def get_job(job):
    """Restore a completed session after the server has restarted. Caller holds lock."""
    if not re.fullmatch(r'[0-9a-f]{32}', job):
        return None
    if job in jobs:
        return jobs[job]
    folder = DATA / job
    try:
        metadata = json.loads((folder / 'job.json').read_text(encoding='utf-8'))
        filename = metadata['filename']
        if not isinstance(filename, str) or Path(filename).name != filename:
            return None
        video = folder / filename
        if not video.is_file():
            return None
        result = json.loads((folder / 'result.json').read_text(encoding='utf-8'))
        review_path = folder / 'review.json'
        if review_path.exists():
            result['shots'] = merge_review(result, json.loads(review_path.read_text(encoding='utf-8')))
            update_totals(result)
        item = {'state': 'done', 'video': str(video), 'progress': 100, 'result': result,
                'hoop_search': 'not_found', 'suggested_hoop': None}
        jobs[job] = item
        return item
    except (OSError, ValueError, KeyError, TypeError):
        app.logger.warning('Could not restore analysis %s', job)
        return None


def update_totals(result):
    shots = result['shots']
    result['attempts'] = len(shots)
    result['makes'] = sum(s['outcome'] == 'made' for s in shots)
    result['misses'] = sum(s['outcome'] == 'missed' for s in shots)
    result['uncertain_shots'] = sum(s['outcome'] == 'uncertain' for s in shots)


def merge_review(result, changes):
    if not isinstance(changes, list) or len(changes) > 1000:
        raise ValueError('Invalid shot list.')
    originals = {s['id']: s for s in result['shots'] if isinstance(s.get('id'), int)}
    used = set()
    shots = []
    duration = result.get('video_duration', 0)
    for entry in changes:
        if not isinstance(entry, dict) or entry.get('outcome') not in ('made', 'missed', 'uncertain'):
            raise ValueError('Invalid shot outcome.')
        source = entry.get('id')
        if source is not None:
            if type(source) is not int or source not in originals or source in used:
                raise ValueError('Invalid shot reference.')
            used.add(source)
            shot = dict(originals[source])
        else:
            seconds = entry.get('seconds')
            if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 <= seconds <= duration + .5:
                raise ValueError('Invalid shot time.')
            shot = {'id': None, 'seconds': round(seconds, 2), 'stages': {}, 'apparent_angle': None,
                    'notes': ['This attempt was added during review. Form measurements are not available.']}
        reviewed = entry.get('reviewed', source is None or entry['outcome'] != shot.get('outcome'))
        shot['outcome'] = entry['outcome']
        shot['reviewed'] = reviewed is True
        shots.append(shot)
    return sorted(shots, key=lambda item: item['seconds'])


@app.get('/')
def home():
    return render_template('index.html')


@app.post('/api/upload')
def upload():
    f = request.files.get('video')
    if not f or not f.filename or Path(f.filename).suffix.lower() not in {'.mp4', '.mov', '.avi', '.m4v'}:
        return jsonify(error='Choose an MP4, MOV, M4V, or AVI video.'), 400
    job = uuid.uuid4().hex
    folder = DATA / job
    folder.mkdir()
    filename = secure_filename(f.filename) or 'video.mp4'
    video = folder / filename
    f.save(video)
    cap = cv2.VideoCapture(str(video))
    ok, frame = cap.read()
    cap.release()
    if not ok:
        shutil.rmtree(folder)
        return jsonify(error='Could not read the video. Try a different file.'), 400
    cv2.imwrite(str(folder / 'preview.jpg'), frame)
    write_json(folder / 'job.json', {'filename': filename})
    with lock:
        jobs[job] = {'state': 'ready', 'video': str(video), 'progress': 0,
                     'hoop_search': 'searching', 'suggested_hoop': None}
    threading.Thread(target=find_hoop, args=(job, video), daemon=True).start()
    return jsonify(id=job, preview='/media/{}/preview.jpg'.format(job), filename=filename)


def find_hoop(job, video):
    result = None
    try:
        if HOOP_PYTHON.is_file() and HOOP_GRAPH.is_file():
            with hoop_processing:
                proc = subprocess.run(
                    [str(HOOP_PYTHON), str(ROOT / 'hoop_worker.py'), str(video), str(HOOP_GRAPH)],
                    capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if proc.returncode == 0:
                result = json.loads(proc.stdout.strip().splitlines()[-1]).get('hoop')
            else:
                app.logger.warning('Hoop detection failed: %s', proc.stderr[-1000:])
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        app.logger.exception('Hoop detection unavailable')
    with lock:
        if job in jobs:
            jobs[job].update(hoop_search='found' if result else 'not_found', suggested_hoop=result)


@app.post('/api/analyze/<job>')
def start(job):
    with lock:
        item = get_job(job)
        if not item:
            abort(404)
        if item['state'] != 'ready':
            return jsonify(error='This video is already being analyzed.'), 409
        data = request.get_json(silent=True) or {}
        hoop = data.get('hoop')
        if hoop is not None:
            if (not isinstance(hoop, list) or len(hoop) != 4 or
                    not all(isinstance(v, (int, float)) and 0 <= v <= 1 for v in hoop) or
                    hoop[2] - hoop[0] < .01 or hoop[3] - hoop[1] < .005):
                return jsonify(error='Draw a valid rectangle around the hoop.'), 400
        if not processing.acquire(blocking=False):
            active = next((key for key, value in jobs.items() if value.get('state') == 'running'), None)
            return jsonify(error='Another video is being analyzed. Returning to its progress.', active_job=active), 409
        item.update(state='running', progress=1, message='Preparing your analysis')
        video = item['video']

    def run():
        def progress(percent, message):
            with lock:
                jobs[job].update(progress=percent, message=message)
        try:
            result = analyze(video, DATA / job, hoop, progress)
            write_json(DATA / job / 'result.json', result)
            with lock:
                jobs[job].update(state='done', progress=100, result=result)
        except Exception as exc:
            app.logger.exception('Analysis failed')
            with lock:
                jobs[job].update(state='error', error=str(exc))
        finally:
            processing.release()
    threading.Thread(target=run, daemon=True).start()
    return jsonify(ok=True)


@app.get('/api/jobs/<job>')
def job_status(job):
    with lock:
        item = get_job(job)
        if not item:
            abort(404)
        return jsonify({k: v for k, v in item.items() if k != 'video'})


@app.put('/api/jobs/<job>/review')
def save_review(job):
    data = request.get_json(silent=True)
    with lock:
        item = get_job(job)
        if not item:
            abort(404)
        if item['state'] != 'done':
            return jsonify(error='Analysis is not ready.'), 409
        try:
            base = json.loads((DATA / job / 'result.json').read_text(encoding='utf-8'))
            changes = data.get('shots') if isinstance(data, dict) else None
            shots = merge_review(base, changes)
            write_json(DATA / job / 'review.json', changes)
            item['result']['shots'] = shots
            update_totals(item['result'])
        except (ValueError, KeyError, TypeError):
            return jsonify(error='Could not save this review. Please try again.'), 400
        except OSError:
            app.logger.exception('Could not save review')
            return jsonify(error='Could not save this review. Please try again.'), 500
    return jsonify(ok=True)


@app.get('/api/jobs/<job>/video')
def video_file(job):
    with lock:
        item = get_job(job)
        if not item:
            abort(404)
        path = item['video']
    return send_file(path, conditional=True)


@app.get('/media/<job>/<path:filename>')
def media(job, filename):
    if not (len(job) == 32 and all(c in '0123456789abcdef' for c in job)):
        abort(404)
    if filename not in {'preview.jpg', 'load.jpg', 'release.jpg', 'follow.jpg', 'trajectory.jpg'} and not re.fullmatch(r'shot_[0-9]+_(load|release|follow)(_original)?\.jpg', filename):
        abort(404)
    return send_from_directory(DATA / job, filename)


@app.errorhandler(413)
def too_large(_):
    return jsonify(error='Video is too large. The limit is 200 MB.'), 413


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5050, debug=False, threaded=True)
