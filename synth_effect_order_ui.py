"""Drag handles and insertion feedback for the existing compact effect rows."""
from PySide6.QtCore import QMimeData, QPoint, QTimer, Qt, Signal
from PySide6.QtGui import QCursor, QDrag, QPainter, QPen
from PySide6.QtWidgets import QApplication, QMenu, QScrollArea, QToolButton, QWidget

MIME = 'application/x-nebula-effect-order'


class EffectDragHandle(QToolButton):
    stepRequested = Signal(str, int)

    def __init__(self, identifier, label, parent):
        super().__init__(parent)
        self.identifier = identifier
        self.rack = None
        self.press = None
        self.dragged = False
        # Paint the grip: the compact theme's padding can clip a text glyph,
        # and not every platform font contains a six-dot handle.
        self.setText('')
        self.setFixedWidth(24)
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
        if not self.rack: return
        ids = self.rack.identifiers
        if self.identifier not in ids: return
        menu = QMenu(self)
        for label, delta in (('Move earlier', -1), ('Move later', 1)):
            action = menu.addAction(label)
            action.setEnabled(0 <= ids.index(self.identifier) + delta < len(ids))
            action.triggered.connect(lambda _checked=False, delta=delta: self.stepRequested.emit(self.identifier, delta))
        menu.exec(self.mapToGlobal(QPoint(0, self.height())))

    def mousePressEvent(self, event):
        self.press = event.position().toPoint() if event.button() == Qt.MouseButton.LeftButton else None
        self.dragged = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (self.press is not None and self.rack and event.buttons() & Qt.MouseButton.LeftButton and
                (event.position().toPoint() - self.press).manhattanLength() >= QApplication.startDragDistance()):
            self.press = None; self.dragged = True; self.setDown(False)
            self.drag_context = self.rack.context
            drag = QDrag(self); mime = QMimeData()
            mime.setData(MIME, self.identifier.encode('utf-8')); drag.setMimeData(mime)
            drag.setPixmap(self.parentWidget().grab())
            drag.setHotSpot(QPoint(12, self.height() // 2))
            drag.exec(Qt.DropAction.MoveAction)
            self.rack.marker = None; self.rack.scroll_timer.stop(); self.rack.update()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.press = None
        if self.dragged:
            self.dragged = False; self.setDown(False); event.accept(); return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.AltModifier and event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            self.stepRequested.emit(self.identifier, -1 if event.key() == Qt.Key.Key_Up else 1)
            event.accept(); return
        super().keyPressEvent(event)


class EffectRack(QWidget):
    reorderRequested = Signal(str, object)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.identifiers = []
        self.rows = {}
        self.context = None
        self.marker = None
        self.scroll_timer = QTimer(self)
        self.scroll_timer.setInterval(30)
        self.scroll_timer.timeout.connect(self.scroll_drag)

    def configure(self, identifiers, rows, context):
        self.identifiers = list(identifiers)
        self.rows = rows
        self.context = (context, tuple(identifiers))
        self.marker = None
        self.scroll_timer.stop()
        self.update()

    def scroll_drag(self):
        area = self.parentWidget()
        while area is not None and not isinstance(area, QScrollArea): area = area.parentWidget()
        if area is None: return
        y = area.viewport().mapFromGlobal(QCursor.pos()).y()
        direction = -1 if y < 28 else 1 if y > area.viewport().height() - 28 else 0
        if direction:
            bar = area.verticalScrollBar(); bar.setValue(bar.value() + direction * 12)
            _, self.marker = self.insertion(self.mapFromGlobal(QCursor.pos()).y())
            self.update()

    def accepts(self, event):
        source = event.source()
        return (isinstance(source, EffectDragHandle) and source.rack is self and
                source.drag_context == self.context and source.identifier in self.identifiers and
                event.mimeData().hasFormat(MIME))

    def insertion(self, y):
        for key in self.identifiers:
            row = self.rows[key]
            if y < row.y() + row.height() / 2:
                return key, max(1, row.y() - 2)
        last = self.rows[self.identifiers[-1]]
        return None, min(self.height() - 2, last.y() + last.height() + 1)

    def dragEnterEvent(self, event):
        if self.accepts(event): event.setDropAction(Qt.DropAction.MoveAction); event.accept()
        else: event.ignore()

    def dragMoveEvent(self, event):
        if not self.accepts(event): event.ignore(); return
        self.scroll_timer.start()
        _, self.marker = self.insertion(event.position().y())
        self.update(); event.setDropAction(Qt.DropAction.MoveAction); event.accept()

    def dragLeaveEvent(self, event):
        self.scroll_timer.stop()
        self.marker = None; self.update(); event.accept()

    def dropEvent(self, event):
        self.scroll_timer.stop()
        self.marker = None; self.update()
        if not self.accepts(event): event.ignore(); return
        before, _ = self.insertion(event.position().y())
        event.setDropAction(Qt.DropAction.MoveAction); event.accept()
        self.reorderRequested.emit(event.source().identifier, before)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.marker is not None:
            painter = QPainter(self)
            painter.setPen(QPen(self.palette().highlight().color(), 2))
            painter.drawLine(0, self.marker, self.width(), self.marker)
