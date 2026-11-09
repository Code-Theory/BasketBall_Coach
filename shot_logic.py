"""Temporal shot recognition based on observable ball and pose measurements."""
from collections import deque
import math


class ShotRecognizer:
    def __init__(self, width, height, hoop=None):
        self.width, self.height, self.hoop = width, height, hoop
        self.scale = min(width, height)
        self.history = deque()
        self.shots = []
        self.active = None
        self.last_release = -10.0

    def observe(self, obs):
        t = obs['time']
        while self.history and t - self.history[0]['time'] > 1.5:
            self.history.popleft()
        ball = obs['ball']
        if self.active:
            shot = self.active
            if ball is not None:
                shot['flight'].append((t, ball, obs.get('hoop', self.hoop)))
            if shot['follow'] is None and t - shot['time'] >= .15 and obs['values']:
                shot['follow'] = obs
            if t - shot['time'] >= 3.0:
                self.active = None
        # Compare observations of the same shooting hand over a short interval.
        if ball is not None and obs['values'] and t - self.last_release >= .8:
            side = obs['values']['side']
            dist = obs['values']['distance']
            for old in reversed(self.history):
                dt = t - old['time']
                if dt > .30:
                    break
                v = old['values']
                if (dt > 0 and old['ball'] is not None and v and v['side'] == side
                        and v['distance'] is not None and dist is not None
                        and v['distance'] < .20 * self.scale
                        and dist - v['distance'] > .03 * self.scale
                        and obs['values']['wrist_above_shoulder'] is True
                        and ball[1] < old['ball'][1] - .01 * self.scale):
                    loads = [o for o in self.history if o['side_values'].get(side) and
                             o['side_values'][side]['knee'] is not None]
                    load = min(loads, key=lambda o: o['side_values'][side]['knee']) if loads else None
                    shot = {'time': old['time'], 'side': side, 'load': load, 'release': old,
                            'follow': None, 'flight': [(old['time'], old['ball'], old.get('hoop', self.hoop)), (t, ball, obs.get('hoop', self.hoop))]}
                    self.shots.append(shot)
                    self.active = shot
                    self.last_release = t
                    break
        self.history.append(obs)

    def outcome(self, shot):
        if not self.hoop:
            return 'uncertain'
        for (ta, a, ha), (tb, b, hb) in zip(shot['flight'], shot['flight'][1:]):
            if ha is None or hb is None or tb - ta > .25:
                continue
            x1, y1, x2, y2 = hb
            center, rim_y = (x1+x2)*self.width/2, (y1+y2)*self.height/2
            hoop_width = (x2-x1)*self.width
            if not (a[1] < rim_y <= b[1]) or b[1] <= a[1]:
                continue
            x = a[0] + (b[0]-a[0]) * (rim_y-a[1]) / (b[1]-a[1])
            if abs(x-center) <= hoop_width*.5:
                return 'made'
            if abs(x-center) <= hoop_width*1.5:
                return 'missed'
        return 'uncertain'

    @staticmethod
    def apparent_angle(shot):
        flight = shot['flight']
        if len(flight) < 3:
            return None
        t0, a, _ = flight[0]
        for t, b, _ in flight[2:]:
            if t-t0 > .45:
                break
            dx, dy = b[0]-a[0], a[1]-b[1]
            if abs(dx) > 5 and dy > 5:
                return round(math.degrees(math.atan2(dy, abs(dx))), 1)
        return None
