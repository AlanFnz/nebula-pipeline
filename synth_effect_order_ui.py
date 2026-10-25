"""Drag handles and insertion feedback for the existing compact effect rows."""
from PySide6.QtCore import QPoint, QTimer, Qt, Signal
from PySide6.QtGui import QCursor, QPainter, QPen
from PySide6.QtWidgets import QApplication, QMenu, QPushButton, QScrollArea, QWidget


class EffectDragHandle(QPushButton):
    stepRequested = Signal(str, int)

    def __init__(self, identifier, label, parent):
        super().__init__(parent)
        self.identifier = identifier
        self.rack = None
        self.press = None
        self.dragged = False
        self.drag_context = None
        self.move_menu = None
        # Paint the grip without relying on platform fonts or text padding.
        self.setText('')
        self.setFixedWidth(24)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setProperty('compact', True)
        self.setAccessibleName('Move ' + label)
        self.setToolTip('Drag to reorder. Click for move commands. Option + Up/Down also moves this effect.')
        self.clicked.connect(self.open_menu)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(self.palette().buttonText())
        for x in (-3, 3):
            for y in (-4, 0, 4):
                painter.drawEllipse(QPoint(self.width() // 2 + x, self.height() // 2 + y), 1, 1)

    def open_menu(self):
        if self.rack is None: return
        ids = self.rack.identifiers
        if self.identifier not in ids: return
        if self.move_menu is not None: self.move_menu.deleteLater()
        self.move_menu = menu = QMenu(self)
        for label, delta in (('Move earlier', -1), ('Move later', 1)):
            action = menu.addAction(label)
            action.setEnabled(0 <= ids.index(self.identifier) + delta < len(ids))
            action.triggered.connect(lambda _checked=False, delta=delta: self.stepRequested.emit(self.identifier, delta))
        menu.popup(self.mapToGlobal(QPoint(0, self.height())))

    def mousePressEvent(self, event):
        self.press = event.globalPosition().toPoint() if event.button() == Qt.MouseButton.LeftButton else None
        self.dragged = False
        self.drag_context = self.rack.context if self.rack is not None else None
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.press is not None and self.rack is not None and event.buttons() & Qt.MouseButton.LeftButton:
            if (event.globalPosition().toPoint() - self.press).manhattanLength() >= QApplication.startDragDistance():
                self.dragged = True
            if self.dragged:
                self.setDown(False)
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                self.rack.move_drag(self, event.globalPosition().toPoint())
                event.accept(); return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.press = None
        if self.dragged:
            self.dragged = False; self.setDown(False)
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            if self.rack is not None: self.rack.finish_drag(self, event.globalPosition().toPoint())
            event.accept(); return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and self.dragged:
            # Keep dragged set until release so cancellation cannot open a menu.
            self.press = None; self.drag_context = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            if self.rack is not None: self.rack.cancel_drag()
            event.accept(); return
        if event.modifiers() & Qt.KeyboardModifier.AltModifier and event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            self.stepRequested.emit(self.identifier, -1 if event.key() == Qt.Key.Key_Up else 1)
            event.accept(); return
        super().keyPressEvent(event)


class EffectRack(QWidget):
    reorderRequested = Signal(str, object)

    def __init__(self):
        super().__init__()
        self.identifiers = []
        self.rows = {}
        self.context = None
        self.marker = None
        self.drag_source = None
        self.scroll_timer = QTimer(self)
        self.scroll_timer.setInterval(30)
        self.scroll_timer.timeout.connect(self.scroll_drag)

    def configure(self, identifiers, rows, context):
        self.identifiers = list(identifiers)
        self.rows = rows
        self.context = (context, tuple(identifiers))
        self.cancel_drag()

    def scroll_area(self):
        area = self.parentWidget()
        while area is not None and not isinstance(area, QScrollArea): area = area.parentWidget()
        return area

    def scroll_drag(self):
        area = self.scroll_area()
        if area is None or self.drag_source is None: return
        y = area.viewport().mapFromGlobal(QCursor.pos()).y()
        direction = -1 if y < 28 else 1 if y > area.viewport().height() - 28 else 0
        if direction:
            bar = area.verticalScrollBar(); bar.setValue(bar.value() + direction * 12)
            self.move_drag(self.drag_source, QCursor.pos())

    def accepts(self, source):
        return (source.rack is self and source.drag_context == self.context and
                source.identifier in self.identifiers)

    def insertion(self, y):
        for key in self.identifiers:
            row = self.rows[key]
            if y < row.y() + row.height() / 2:
                return key, max(1, row.y() - 2)
        last = self.rows[self.identifiers[-1]]
        return None, min(self.height() - 2, last.y() + last.height() + 1)

    def inside(self, position):
        if not self.rect().contains(self.mapFromGlobal(position)): return False
        area = self.scroll_area()
        return area is None or area.viewport().rect().contains(area.viewport().mapFromGlobal(position))

    def move_drag(self, source, position):
        if not self.accepts(source): self.cancel_drag(); return
        self.drag_source = source
        if self.inside(position):
            self.scroll_timer.start()
            _, self.marker = self.insertion(self.mapFromGlobal(position).y())
        else:
            self.scroll_timer.stop(); self.marker = None
        self.update()

    def cancel_drag(self):
        self.scroll_timer.stop()
        self.drag_source = None
        self.marker = None; self.update()

    def finish_drag(self, source, position):
        self.cancel_drag()
        if not self.accepts(source) or not self.inside(position): return
        before, _ = self.insertion(self.mapFromGlobal(position).y())
        self.reorderRequested.emit(source.identifier, before)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.marker is not None:
            painter = QPainter(self)
            painter.setPen(QPen(self.palette().highlight().color(), 2))
            painter.drawLine(0, self.marker, self.width(), self.marker)
