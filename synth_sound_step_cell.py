"""Compact, keyboard-accessible step overview; precise values live in the editor."""
from PySide6.QtCore import Qt, Signal, QRectF, QSize, QPointF, QSignalBlocker
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QAbstractButton
from studio_theme import COLORS


class StepCell(QAbstractButton):
    selected = Signal(int)
    edited = Signal(int, str, object)
    navigate = Signal(int)
    editRequested = Signal()
    gestureStarted = Signal()
    gestureFinished = Signal()

    def __init__(self, index, parent=None):
        super().__init__(parent)
        self.index = index; self.entry = {}; self.note = ''; self.in_pattern = True
        self.playing = False; self.drag_key = None
        self.setCheckable(True); self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumWidth(32); self.setFixedHeight(196)
        self.clicked.connect(lambda: self.selected.emit(self.index))
        self.toggled.connect(self.accessible_selection)
        self.setToolTip('Click the number to select. Drag a note or level up/down. Shift: fine adjustment. Left/right: select a step. Enter: edit. Space: toggle rest.')

    def sizeHint(self): return QSize(40, 196)
    def minimumSizeHint(self): return QSize(32, 196)

    def nextCheckState(self):
        # Selection belongs to the sequencer, including accessibility presses.
        # Pressing the already-selected step must not uncheck its highlight.
        pass

    def accessible_selection(self, _):
        # macOS accessibility can toggle a checkable button directly, without
        # sending clicked or focus events. Route that action through selection.
        self.selected.emit(self.index)
        with QSignalBlocker(self): self.setChecked(True)

    def show_step(self, entry, note, in_pattern, selected, playing):
        self.entry = entry; self.note = note; self.in_pattern = in_pattern; self.playing = playing
        with QSignalBlocker(self): self.setChecked(selected)
        state = 'On' if entry['enabled'] else 'Rest'
        self.setAccessibleName(f'Step {self.index + 1}')
        self.setAccessibleDescription(f"{state}; {note}; {entry['semitones']:+d} semitones; velocity {entry['velocity']*100:g}%; gate {entry['gate']*100:g}%. " + ('In pattern.' if in_pattern else 'Outside pattern; values retained.'))
        self.update()

    def paintEvent(self, _):
        if not self.entry: return
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.fillRect(r, QColor(COLORS['selected'] if self.isChecked() else COLORS['input']))
        color = QColor(COLORS['text'] if self.in_pattern else COLORS['disabled'])
        p.setPen(color)
        font = p.font(); font.setPixelSize(11); p.setFont(font)
        p.drawText(QRectF(0, 2, self.width(), 20), Qt.AlignmentFlag.AlignCenter, str(self.index + 1))
        p.drawText(QRectF(0, 24, self.width(), 20), Qt.AlignmentFlag.AlignCenter, 'On' if self.entry['enabled'] else '—')
        p.drawText(QRectF(0, 46, self.width(), 20), Qt.AlignmentFlag.AlignCenter, self.note)
        bar_color = QColor(COLORS['accent'] if self.in_pattern and self.entry['enabled'] else COLORS['disabled'])
        # Pitch contour, then two aligned level lanes. Rest and out-of-length
        # steps retain their contour, so extending a pattern is predictable.
        p.fillRect(QRectF(self.width()/2-3, 69, 6, 61), QColor(COLORS['border']))
        height = (self.entry['semitones'] + 12) / 36 * 59 + 2
        p.fillRect(QRectF(self.width()/2-3, 130-height, 6, height), bar_color)
        for key, top in (('velocity', 136), ('gate', 166)):
            p.setPen(color)
            p.drawText(QRectF(0, top, self.width(), 20), Qt.AlignmentFlag.AlignCenter, f"{self.entry[key]*100:.0f}%")
            p.fillRect(QRectF(4, top+22, self.width()-8, 3), QColor(COLORS['border']))
            p.fillRect(QRectF(4, top+22, (self.width()-8)*self.entry[key], 3), bar_color)
        if self.isChecked():
            p.setPen(QPen(QColor(COLORS['accent']), 2)); p.drawRect(r)
        if self.hasFocus():
            p.setPen(QPen(QColor(COLORS['text']), 1, Qt.PenStyle.DotLine)); p.drawRect(r.adjusted(3, 3, -3, -3))
        if self.playing:
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(COLORS['cursor']))
            p.drawPolygon(QPolygonF([QPointF(3, 4), QPointF(9, 8), QPointF(3, 12)]))
            p.fillRect(QRectF(2, 193, self.width()-4, 2), QColor(COLORS['cursor']))
        p.end()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton: return
        self.setFocus(Qt.FocusReason.MouseFocusReason); self.selected.emit(self.index)
        y = event.position().y()
        if 24 <= y < 44:
            self.gestureStarted.emit()
            self.edited.emit(self.index, 'enabled', not self.entry['enabled'])
            self.gestureFinished.emit()
        elif y >= 46:
            self.drag_key = 'semitones' if y < 134 else 'velocity' if y < 164 else 'gate'
            self.drag_y = y; self.drag_value = self.entry[self.drag_key]
            self.gestureStarted.emit()
        event.accept()

    def mouseMoveEvent(self, event):
        if self.drag_key is None: return
        delta = self.drag_y - event.position().y()
        if not delta: return
        fine = .1 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1.
        if self.drag_key == 'semitones': value = max(-12, min(24, round(self.drag_value + delta*fine/4)))
        else:
            low = .1 if self.drag_key == 'gate' else 0.
            value = max(low, min(1., round(self.drag_value + delta*fine/80, 4)))
        self.edited.emit(self.index, self.drag_key, value)

    def mouseReleaseEvent(self, event):
        if self.drag_key is not None:
            self.drag_key = None; self.gestureFinished.emit()
        event.accept()

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Home, Qt.Key.Key_End):
            target = 0 if key == Qt.Key.Key_Home else 15 if key == Qt.Key.Key_End else self.index + (1 if key == Qt.Key.Key_Right else -1)
            self.navigate.emit(max(0, min(15, target)))
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter): self.editRequested.emit()
        elif key == Qt.Key.Key_Space:
            self.edited.emit(self.index, 'enabled', not self.entry['enabled'])
        else:
            super().keyPressEvent(event); return
        event.accept()

    def focusInEvent(self, event):
        super().focusInEvent(event); self.selected.emit(self.index); self.update()

    def focusOutEvent(self, event):
        super().focusOutEvent(event); self.update()
