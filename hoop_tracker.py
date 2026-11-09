"""Track a manually confirmed rim box as a camera pans or tilts."""
import cv2


class HoopTracker:
    def __init__(self, frame, hoop):
        self.height, self.width = frame.shape[:2]
        x1, y1, x2, y2 = hoop
        x1, x2 = round(x1*self.width), round(x2*self.width)
        y1, y2 = round(y1*self.height), round(y2*self.height)
        margin = round((x2-x1)*.75)
        self.x = max(0, x1-margin)
        self.y = max(0, y1-(y2-y1)*5)
        right = min(self.width, x2+margin)
        bottom = min(self.height, y2+(y2-y1)*2)
        self.template = cv2.cvtColor(frame[self.y:bottom, self.x:right], cv2.COLOR_BGR2GRAY)
        self.th, self.tw = self.template.shape[:2]
        self.offset = (x1-self.x, y1-self.y, x2-self.x, y2-self.y)
        self.initial = tuple(hoop)
        self.first = True

    def update(self, frame):
        if self.first:
            self.first = False
            return self.initial
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        dx, dy = round(self.width*.14), round(self.height*.14)
        left, top = max(0, self.x-dx), max(0, self.y-dy)
        right, bottom = min(self.width, self.x+self.tw+dx), min(self.height, self.y+self.th+dy)
        region = gray[top:bottom, left:right]
        if self.tw < 2 or self.th < 2 or region.shape[0] < self.th or region.shape[1] < self.tw:
            return None
        result = cv2.matchTemplate(region, self.template, cv2.TM_CCOEFF_NORMED)
        _, confidence, _, position = cv2.minMaxLoc(result)
        if confidence < .60:
            return None
        self.x, self.y = left+position[0], top+position[1]
        x1, y1, x2, y2 = self.offset
        return ((self.x+x1)/self.width, (self.y+y1)/self.height,
                (self.x+x2)/self.width, (self.y+y2)/self.height)
