"""Integration tests for the vendored tracker and CourtVision adapter."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tracker_bridge import ShotTrackerBridge
from vendor.shottracker.sim import DEFAULT_HOOP, ShotSpec, simulate_stream

class BridgeTests(unittest.TestCase):
    def test_tracks_synthetic_make(self):
        bridge = ShotTrackerBridge(1280, 720)
        box = [DEFAULT_HOOP.x1/1280, 157.5/720, DEFAULT_HOOP.x2/1280, 163.5/720]
        for t, obs in simulate_stream(DEFAULT_HOOP, [ShotSpec(offset=0.0)]):
            candidates = [] if obs is None else [((obs.x-20, obs.y-20, obs.x+20, obs.y+20), .9)]
            bridge.step(t, candidates, box)
        self.assertEqual(len(bridge.events), 1, bridge.judge.log)
        shots = [{'seconds': bridge.events[0].t_release, 'outcome': 'uncertain'}]
        bridge.match(shots)
        self.assertEqual(shots[0]['outcome'], 'made' if bridge.events[0].method in ('interpolated', 'rebound') else 'uncertain')
        self.assertIn(shots[0]['tracking']['method'], ('interpolated', 'fit', 'extrapolated'))

    def test_extrapolated_event_remains_uncertain(self):
        from types import SimpleNamespace
        from vendor.shottracker.types import Outcome
        bridge = ShotTrackerBridge(1280, 720)
        bridge.events = [SimpleNamespace(t_release=1, t_cross=2, outcome=Outcome.MADE, method='extrapolated', reason='through_hoop')]
        shots = [{'seconds': 1.0, 'outcome': 'uncertain'}]
        bridge.match(shots)
        self.assertEqual(shots[0]['outcome'], 'uncertain')
        self.assertEqual(shots[0]['tracking']['method'], 'extrapolated')

    def test_unmatched_release_remains_uncertain(self):
        bridge = ShotTrackerBridge(1280, 720)
        shots = [{'seconds': 1.0, 'outcome': 'uncertain'}]
        bridge.match(shots)
        self.assertEqual(shots[0]['outcome'], 'uncertain')

if __name__ == '__main__':
    unittest.main()
