"""Verify the rim follows a panning camera and fails safely when the view is lost."""
import sys
import unittest
from pathlib import Path
import cv2
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hoop_tracker import HoopTracker

class HoopTrackerTests(unittest.TestCase):
    def test_translation_and_loss(self):
        rng = np.random.default_rng(19)
        frame = rng.integers(0, 255, size=(240, 320, 3), dtype=np.uint8)
        box = (.45, .42, .55, .48)
        tracker = HoopTracker(frame, box)
        self.assertEqual(tracker.update(frame), box)
        # Camera shift: 18 pixels right and 11 pixels down.
        transform = np.float32([[1, 0, 18], [0, 1, 11]])
        moved = cv2.warpAffine(frame, transform, (320, 240))
        result = tracker.update(moved)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result[0] - box[0], 18/320, delta=.01)
        self.assertAlmostEqual(result[1] - box[1], 11/240, delta=.01)
        self.assertIsNone(tracker.update(np.zeros_like(frame)))

if __name__ == '__main__':
    unittest.main()
