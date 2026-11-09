"""Exercise upload, asynchronous analysis and results using a supplied video."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app

video = Path(sys.argv[1])
with app.test_client() as client:
    assert client.get('/').status_code == 200
    assert client.post('/api/upload', data={}).status_code == 400
    with video.open('rb') as stream:
        response = client.post('/api/upload', data={'video': (stream, video.name)}, content_type='multipart/form-data')
    assert response.status_code == 200, response.data
    job = response.json['id']
    assert client.get(response.json['preview']).status_code == 200
    assert client.post('/api/analyze/' + job, json={'hoop': [1, 1, 0, 0]}).status_code == 400
    deadline = time.monotonic() + 150
    while time.monotonic() < deadline:
        status = client.get('/api/jobs/' + job).json
        if status['hoop_search'] != 'searching':
            break
        time.sleep(.5)
    assert status['hoop_search'] == 'found', status
    box = status['suggested_hoop']
    assert .54 < box[0] < .58 and .59 < box[2] < .63, box
    assert .34 < box[1] < .39 and .38 < box[3] < .41, box
    assert client.post('/api/analyze/' + job, json={'hoop': box}).status_code == 200
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        result = client.get('/api/jobs/' + job).json
        if result['state'] in ('done', 'error'):
            break
        time.sleep(.2)
    assert result['state'] == 'done', result
    data = result['result']
    assert data['processed_frames'] > 0 and data['ball_frames'] > 0, data
    assert data['stages'].get('release'), data
    assert data['attempts'] == len(data['shots']) >= 1, data
    assert data['uncertain_shots'] >= 1, 'The sample ball disappears near the rim and should be flagged as uncertain.'
    assert client.get('/media/' + job + '/' + data['trajectory']).status_code == 200
    assert client.get('/api/jobs/' + job + '/video').status_code == 200
    for stage in data['stages'].values():
        assert client.get('/media/' + job + '/' + stage['image']).status_code == 200
    print('UPLOAD TO RESULTS PASSED:', data)
