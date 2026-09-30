"""View-only zoom and panning, independent of preview/export resolution."""
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QWidget

from studio_theme import COLORS, terminal_font


class SynthViewer(QWidget):
    zoomChanged = Signal(float)

    def __init__(self):
        super().__init__()
        self.packet = None
        self.canvas_size = (720, 576)
        self.zoom = 0.  # Fit; positive values are canvas pixels per view point.
        self.pan = QPointF()
        self.drag_position = None
        self.setMinimumSize(320, 240)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setToolTip('Zoom changes only this view. Drag to pan when zoomed in. Double-click to fit. Ctrl/⌘ + wheel zooms.')

    def set_packet(self, packet):
        self.packet = packet
        self.update()

    def set_canvas_size(self, size):
        if tuple(size) != self.canvas_size:
            self.canvas_size = tuple(size)
            self.pan = QPointF()
            self.update()

    def display_scale(self):
        return self.zoom or min(self.width() / self.canvas_size[0], self.height() / self.canvas_size[1])

    def target_rect(self):
        scale = self.display_scale()
        width, height = (edge * scale for edge in self.canvas_size)
        return QRectF((self.width() - width) / 2 + self.pan.x(), (self.height() - height) / 2 + self.pan.y(), width, height)

    def clamp_pan(self):
        scale = self.display_scale()
        dx = max(0., (self.canvas_size[0] * scale - self.width()) / 2)
        dy = max(0., (self.canvas_size[1] * scale - self.height()) / 2)
        self.pan = QPointF(max(-dx, min(dx, self.pan.x())), max(-dy, min(dy, self.pan.y())))
        self.setCursor(Qt.CursorShape.OpenHandCursor if dx or dy else Qt.CursorShape.ArrowCursor)

    def set_zoom(self, zoom, anchor=None):
        previous = self.display_scale()
        point = anchor or QPointF(self.width() / 2, self.height() / 2)
        center = QPointF(self.width() / 2, self.height() / 2)
        self.zoom = max(.05, min(8., float(zoom))) if zoom else 0.
        ratio = self.display_scale() / max(.0001, previous)
        self.pan = (self.pan + center - point) * ratio + point - center if self.zoom else QPointF()
        self.clamp_pan(); self.update(); self.zoomChanged.emit(self.zoom * 100)

    def zoom_by(self, factor, anchor=None):
        self.set_zoom(self.display_scale() * factor, anchor)

    def paintEvent(self, event):
        painter = QPainter(self); painter.fillRect(self.rect(), QColor(COLORS['monitor']))
        if not self.packet:
            painter.setPen(QColor(COLORS['muted'])); painter.setFont(terminal_font())
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, '> awaiting signal\n\nLuminous sources / irregular blinds')
            return
        (w, h), raw = self.packet
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawImage(self.target_rect(), QImage(raw, w, h, w * 3, QImage.Format.Format_RGB888))

    def resizeEvent(self, event):
        self.clamp_pan(); super().resizeEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.position(); self.setCursor(Qt.CursorShape.ClosedHandCursor); event.accept()

    def mouseMoveEvent(self, event):
        if self.drag_position is not None:
            self.pan += event.position() - self.drag_position
            self.drag_position = event.position(); self.clamp_pan(); self.update(); event.accept()

    def mouseReleaseEvent(self, event):
        self.drag_position = None; self.clamp_pan()

    def mouseDoubleClickEvent(self, event):
        self.set_zoom(0.)

    def wheelEvent(self, event):
        if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
            delta = event.pixelDelta().y() or event.angleDelta().y() / 8
            self.zoom_by(2 ** (delta / 120), event.position())
        else:
            delta = event.pixelDelta() if not event.pixelDelta().isNull() else event.angleDelta() / 4
            self.pan += QPointF(delta); self.clamp_pan(); self.update()
        event.accept()
