"""Small monitor activity feedback; animation never requests a rendered frame."""
import time

from PySide6.QtCore import QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QPainter, QPen

from synth_workspace_widgets import ElidingLabel


class MonitorStatus(ElidingLabel):
    def __init__(self, text, activity):
        self.activity = activity
        self.mode = 'idle'
        self.detail = text
        self.animation = None
        super().__init__(text)
        self.setContentsMargins(21, 0, 0, 0)
        self.animation = QTimer(self)
        self.animation.setInterval(100)
        self.animation.timeout.connect(lambda: self.update(QRect(0, 0, 18, self.height())))

    def setText(self, text):
        self.detail = text
        self.refresh()

    def refresh(self):
        self.mode, caption = self.activity()
        super().setText(caption or self.detail)
        self._animate()
        self.update()

    def _animate(self):
        if self.animation is None: return
        active = self.mode == 'loading' and self.isVisible()
        if active and not self.animation.isActive(): self.animation.start()
        elif not active: self.animation.stop()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()

    def hideEvent(self, event):
        if self.animation: self.animation.stop()
        super().hideEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.mode == 'idle': return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self.palette().windowText().color(), 1.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        y = self.height()/2
        if self.mode == 'loading':
            painter.drawArc(QRectF(2, y-5.5, 11, 11), -int(time.monotonic()*240 % 360)*16, 260*16)
        else:
            painter.drawLine(5, round(y-4), 5, round(y+4))
            painter.drawLine(10, round(y-4), 10, round(y+4))
