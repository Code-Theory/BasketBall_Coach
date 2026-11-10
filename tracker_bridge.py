"""Connect CourtVision detections to the vendored Basketball Shot Tracker."""
from vendor.shottracker.geometry import Box
from vendor.shottracker.shot_logic import ShotDetector
from vendor.shottracker.tracking import BallTracker, StaticSuppressor
from vendor.shottracker.types import Detection


class ShotTrackerBridge:
    def __init__(self, width, height):
        self.width, self.height = width, height
        self.tracker = BallTracker()
        self.static = StaticSuppressor()
        self.judge = ShotDetector()
        self.events = []
        self._had_hoop = False

    def step(self, t, candidates, hoop, in_hand=False):
        if hoop:
            x1, y1, x2, y2 = hoop
            left, right = x1*self.width, x2*self.width
            # CourtVision boxes only the opening; the upstream judge measures its rim line
            # in rim-width units and normally expects a box including the hanging net.
            rim = (y1+y2)*self.height/2
            top = rim - .15*(right-left)
            hoop_box = Box(left, top, right, top + (right-left))
        else:
            hoop_box = None
        if hoop_box is None:
            # Do not let the upstream judge keep using a stale position when tracking is lost.
            if self._had_hoop:
                self.judge = ShotDetector()
            self._had_hoop = False
        else:
            self._had_hoop = True
        detections = [Detection('ball', score, Box(*box)) for box, score in candidates]
        detections = self.static.filter(t, detections)
        ball = self.tracker.update(t, detections, hoop_box)
        if self.tracker.switched:
            self.judge.note_track_switch(t)
        if in_hand:
            self.judge.note_ball_in_hand(t)
        if hoop_box is not None:
            events = self.judge.update(t, ball, hoop_box)
            self.events.extend(events)

    def match(self, shots):
        """Attach a judged event to the nearest release; leave unmatched releases uncertain."""
        unused = set(range(len(shots)))
        for event in sorted(self.events, key=lambda e: e.t_release):
            candidates = [(abs(shots[i]['seconds'] - event.t_release), i) for i in unused]
            if candidates:
                delta, index = min(candidates)
                if delta <= 1.5:
                    shot = shots[index]
                    # Keep the judge's trajectory-based calls, but distinguish estimates
                    # from a directly observed crossing so the UI can flag weak evidence.
                    if event.method in ('interpolated', 'rebound', 'rattle', 'fit', 'extrapolated'):
                        shot['outcome'] = event.outcome.value
                    shot['tracking'] = {'method': event.method, 'reason': event.reason,
                                        'crossing_seconds': round(event.t_cross, 2),
                                        'evidence': 'low' if event.method in ('fit', 'extrapolated') else 'observed'}
                    if event.method in ('fit', 'extrapolated') and 'notes' in shot:
                        shot['notes'].append('Low-evidence outcome estimate: the tracker fitted the ball path near the rim. Watch the video to confirm it.')
                    unused.remove(index)
