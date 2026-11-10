"""Check class mapping and detections for the supported ball models."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis import BallDetector


class FakeSession:
    def run(self, *_):
        # Ball, rim and sports-ball predictions, each in cx, cy, w, h format.
        return [np.array([[[100, 200, 300], [100, 200, 300], [20, 40, 20],
                           [20, 40, 20], [.9, .01, .01], [.01, .99, .01],
                           [.01, .01, .8]]], dtype=np.float32)]


class BallDetectorTests(unittest.TestCase):
    def test_swish_uses_ball_classes_and_ignores_rim(self):
        detector = BallDetector.__new__(BallDetector)
        detector.net, detector.input = FakeSession(), 'image'
        detector.input_h = detector.input_w = 640
        detector.ball_classes = (0, 2)
        ball = detector.detect(np.zeros((640, 640, 3), dtype=np.uint8))
        np.testing.assert_allclose(ball, [100, 100])
        self.assertEqual(len(detector.candidates), 2)
        self.assertTrue(all(not (box[0] < 200 < box[2] and box[1] < 200 < box[3])
                            for box, _ in detector.candidates))

    def test_unknown_model_reports_configuration_error(self):
        with patch.dict(os.environ, {'COURTVISION_BALL_MODEL': 'unknown'}):
            with self.assertRaisesRegex(ValueError, 'standard, fast, or swish'):
                BallDetector()


if __name__ == '__main__':
    unittest.main()
