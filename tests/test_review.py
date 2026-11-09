"""A saved review can be recovered after a server restart."""
import json
import shutil
import sys
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as server

class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.root = server.DATA / ('review-test-' + uuid.uuid4().hex)
        self.root.mkdir()
        self.job = uuid.uuid4().hex
        folder = self.root / self.job
        folder.mkdir()
        (folder / 'clip.mp4').write_bytes(b'video')
        (folder / 'job.json').write_text(json.dumps({'filename': 'clip.mp4'}), encoding='utf-8')
        self.original = {'shots': [{'id': 0, 'seconds': 1.0, 'outcome': 'uncertain', 'stages': {}, 'notes': []}], 'video_duration': 5.0}
        (folder / 'result.json').write_text(json.dumps(self.original), encoding='utf-8')
        self.data_patch = patch.object(server, 'DATA', self.root)
        self.data_patch.start()
        server.jobs.clear()
        self.client = server.app.test_client()

    def tearDown(self):
        server.jobs.clear()
        self.data_patch.stop()
        shutil.rmtree(self.root)

    def test_save_and_restore(self):
        changes = [{'id': 0, 'seconds': 1, 'outcome': 'made'}, {'id': None, 'seconds': 3, 'outcome': 'missed'}]
        response = self.client.put('/api/jobs/' + self.job + '/review', json={'shots': changes})
        self.assertEqual(response.status_code, 200)
        server.jobs.clear()
        result = self.client.get('/api/jobs/' + self.job).json['result']
        self.assertEqual([s['outcome'] for s in result['shots']], ['made', 'missed'])
        self.assertEqual((result['attempts'], result['makes'], result['misses']), (2, 1, 1))
        response = self.client.get('/api/jobs/' + self.job + '/video')
        self.assertEqual(response.status_code, 200)
        response.close()

    def test_rejects_invalid_review(self):
        response = self.client.put('/api/jobs/' + self.job + '/review', json={'shots': [{'id': 77, 'outcome': 'made'}]})
        self.assertEqual(response.status_code, 400)
        response = self.client.put('/api/jobs/' + self.job + '/review', json={'shots': [{'id': None, 'seconds': 99, 'outcome': 'made'}]})
        self.assertEqual(response.status_code, 400)
        self.assertFalse((self.root / self.job / 'review.json').exists())

if __name__ == '__main__':
    unittest.main()
