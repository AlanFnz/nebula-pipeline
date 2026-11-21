"""Small monitor activity feedback; animation never requests a rendered frame."""
import time

from PySide6.QtCore import QRect, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QLabel

from nebula.ui.studio_theme import COLORS
from nebula.ui.synth_workspace_widgets import ElidingLabel


class MonitorFrameStatus(QLabel):
    """Describe the displayed image independently of background preparation."""

    states = {
        'current': ('Up to date', 'accent', 'The displayed frame matches the playhead and the latest visual settings for this view.'),
        'updating': ('Updating', 'warning', 'The frame for this position and these settings is being prepared.'),
        'waiting': ('Waiting', 'warning', 'The previous image is still on screen. The requested frame is waiting to be prepared.'),
        'empty': ('No frame', 'muted', 'There is no frame on the monitor.'),
        'error': ('Unavailable', 'destructive', 'The requested frame could not be displayed. See the preview status for details.'),
    }

    def __init__(self):
        super().__init__()
        self.setObjectName('monitorMeta')
        self.setContentsMargins(12, 0, 0, 0)
        self.state = None
        self.set_state('empty')

    def sizeHint(self):
        # Keep the surrounding controls in place when the wording changes.
        width = max(self.fontMetrics().horizontalAdvance(label) for label, _, _ in self.states.values())
        return QSize(width + self.contentsMargins().left() + 2, super().sizeHint().height())

    def set_state(self, state):
        if state == self.state: return
        self.state = state
        label, _, detail = self.states[state]
        self.setText(label)
        self.setAccessibleName(f'Monitor frame · {label}')
        self.setAccessibleDescription(detail)
        self.setToolTip(detail)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(COLORS[self.states[self.state][1]]))
        painter.drawEllipse(QRectF(1, self.height()/2 - 3.5, 7, 7))


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
