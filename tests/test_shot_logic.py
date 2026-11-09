"""Tests for multi-shot recognition and conservative outcome classification."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shot_logic import ShotRecognizer


def observation(t, ball, distance, high=True):
    values = {'side': 'right', 'distance': distance, 'knee': 125, 'elbow': 130,
              'wrist_above_shoulder': high}
    return {'time': t, 'frame': int(t*30), 'ball': ball, 'values': values,
            'side_values': {'right': values}, 'image': None}


class ShotTests(unittest.TestCase):
    def test_multiple_releases_and_uncertain_without_hoop(self):
        r = ShotRecognizer(1000, 1000)
        for obs in [observation(0, (200, 700), 30), observation(.1, (225, 650), 100),
                    observation(3.2, (200, 700), 30), observation(3.3, (225, 650), 100)]:
            r.observe(obs)
        self.assertEqual(len(r.shots), 2)
        self.assertEqual(r.shots[0]['release']['time'], 0)
        self.assertTrue(all(r.outcome(s) == 'uncertain' for s in r.shots))

    def test_dribble_does_not_become_release(self):
        r = ShotRecognizer(1000, 1000)
        r.observe(observation(0, (200, 700), 30, False))
        r.observe(observation(.1, (220, 750), 100, False))
        self.assertEqual(r.shots, [])

    def test_outcomes_require_nearby_continuous_rim_crossing(self):
        r = ShotRecognizer(1000, 1000, [.45, .48, .55, .52])
        def outcome(a, b, delta=.1):
            return r.outcome({'flight': [(0, a, r.hoop), (delta, b, r.hoop)]})
        self.assertEqual(outcome((500, 450), (500, 550)), 'made')
        self.assertEqual(outcome((590, 450), (590, 550)), 'missed')
        self.assertEqual(outcome((800, 450), (800, 550)), 'uncertain')
        self.assertEqual(outcome((500, 450), (500, 550), .5), 'uncertain')

if __name__ == '__main__':
    unittest.main()
