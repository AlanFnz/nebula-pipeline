"""Direct manipulation in the monitor, using the same editable artwork as export."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QPlainTextEdit

from nebula.documents.synth_composition import compile_composition
from nebula.documents.synth_sequence import render_sequence_frame
from nebula.ui.synth_viewer import SynthViewer
from nebula.sources.synth_text import validate_text


_drafts = ThreadPoolExecutor(max_workers=1, thread_name_prefix='poster-drag')


def _render_draft(doc, seconds, size):
    image = render_sequence_frame(compile_composition(doc), seconds, size)
    return image.size, image.convert('RGB').tobytes()


@dataclass
class Drag:
    key: str
    origin: QPointF
    frame: object
    scope: tuple
    mode: str = 'move'
    delta: tuple = (0., 0.)
    guides: tuple = (None, None)


class CanvasWording(QPlainTextEdit):
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.parentWidget().finish_wording(cancel=True)
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self.parentWidget().finish_wording()
        else:
            return super().keyPressEvent(event)
        event.accept()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        parent = self.parentWidget()
        if parent and parent.word_editor is self and event.reason() != Qt.FocusReason.PopupFocusReason:
            parent.finish_wording()


class PosterViewer(SynthViewer):
    wording_changed = Signal()
    arrows = {Qt.Key.Key_Left: (-1, 0), Qt.Key.Key_Right: (1, 0),
              Qt.Key.Key_Up: (0, -1), Qt.Key.Key_Down: (0, 1)}

    def __init__(self):
        super().__init__()
        self.normal_hint = self.toolTip()
        self.layers = None
        self.move_tool = False
        self.can_edit = lambda: False
        self.can_nudge = lambda: False
        self.word_editor = self.word_context = None
        self.drag = self.draft = self.job = self.submitted = None
        self.timer = QTimer(self)
        self.timer.setInterval(25)
        self.timer.timeout.connect(self._preview_motion)

    def bind(self, panel, can_edit):
        self.finish_wording(cancel=True)
        self.cancel_move()
        if self.layers:
            self.layers.selection_changed.disconnect(self.update)
            self.layers.frame_changed.disconnect(self.cancel_move)
        self.layers = panel
        self.can_edit = can_edit
        if panel:
            panel.selection_changed.connect(self.update)
            panel.frame_changed.connect(self.cancel_move)
        self.set_move_tool(panel is not None)

    def set_move_tool(self, on):
        self.cancel_move()
        self.move_tool = on and self.layers is not None
        self.setToolTip('Drag to move. Double-click lettering to edit. Drag plate corners to scale or the round handle to rotate. '
                        'Arrows move 1 px, Shift moves 10. Hold Option or Alt to ignore guides. Escape cancels.'
                        if self.move_tool else self.normal_hint)
        self.clamp_pan()

    def clamp_pan(self):
        super().clamp_pan()
        if getattr(self, 'move_tool', False):
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def cancel_move(self):
        self.timer.stop()
        self.drag = self.draft = self.submitted = None
        if self.job and self.job.cancel():
            self.job = None
        self.update()

    def _size(self, longest):
        scale = min(1., longest / max(self.canvas_size))
        return tuple(max(1, round(v * scale)) for v in self.canvas_size)

    def _point(self, position):
        rect = self.target_rect()
        return QPointF((position.x() - rect.x()) / rect.width(), (position.y() - rect.y()) / rect.height())

    def _box(self, key):
        size = self._size(1000)
        mask = self.layers.frame.mask(key, size)
        bounds = mask.getbbox() if mask is not None else None
        if bounds:
            x, y, right, bottom = bounds
            r = self.target_rect()
            return QRectF(r.x()+x*r.width()/size[0], r.y()+y*r.height()/size[1],
                          (right-x)*r.width()/size[0], (bottom-y)*r.height()/size[1])

    def _plate_handles(self, frame, key, scale=1., angle=0., offset=(0., 0.)):
        params = frame.modules[frame.by_key[key].owner]
        cx, cy = frame.center(key)
        r = self.target_rect()
        sx, sy = r.width()/self.canvas_size[0], r.height()/self.canvas_size[1]
        radius = params['mask_size'] * frame.reference[1] / 2 * scale
        if key in frame.before_print:
            radius *= frame.dye['scale']
            angle += frame.dye['angle']
        a = math.radians(params['mask_angle'] + angle)
        def point(x, y):
            return QPointF(r.x()+(cx+offset[0]+x*math.cos(a)-y*math.sin(a))*sx,
                           r.y()+(cy+offset[1]+x*math.sin(a)+y*math.cos(a))*sy)
        w = radius * params['mask_aspect']
        corners = [point(x, y) for x, y in ((-w,-radius), (w,-radius), (w,radius), (-w,radius))]
        return corners, point(0, -radius), point(0, -radius - 18 / sy)

    def _gesture(self, position, modifiers):
        drag = self.drag
        p = self._point(position)
        w, h = self.canvas_size
        cx, cy = drag.frame.center(drag.key)
        if drag.mode != 'move':
            ox, oy = drag.origin.x()*w-cx, drag.origin.y()*h-cy
            x, y = p.x()*w-cx, p.y()*h-cy
            if drag.mode == 'scale':
                return max(.001, math.hypot(x, y) / max(.001, math.hypot(ox, oy))), 0.
            return 1., math.degrees(math.atan2(y, x) - math.atan2(oy, ox))
        delta = [(p.x()-drag.origin.x())*w, (p.y()-drag.origin.y())*h]
        guides = [None, None]
        if not modifiers & Qt.KeyboardModifier.AltModifier:
            centers = [drag.frame.center(k) for k in drag.frame.order if k != drag.key and
                       k not in drag.frame.hidden and drag.frame.by_key[k].kind == 'plate']
            centers.append((w/2, h/2))
            for i, (c, edge, pixels) in enumerate(zip((cx, cy), (w, h), (self.target_rect().width(), self.target_rect().height()))):
                if abs(delta[i]) < .01:
                    continue
                nearest = min((other[i] for other in centers), key=lambda v: abs(v-c-delta[i]))
                if abs(nearest-c-delta[i])*pixels/edge <= 5:
                    delta[i], guides[i] = nearest-c, nearest
        drag.guides = tuple(guides)
        return tuple(delta)

    def mousePressEvent(self, event):
        if not self.move_tool or event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)
        event.accept()
        if not self.packet or not self.can_edit():
            return
        self.setFocus()
        layers = self.layers
        layers.composer.look_tabs.setCurrentWidget(layers)
        layers.refresh()
        p = self._point(event.position())
        frame = layers.frame
        mode = 'move'
        key = layers.selected
        if key in frame.order and key not in frame.hidden and frame.by_key[key].kind == 'plate':
            corners, _, rotate = self._plate_handles(frame, key)
            if (rotate-event.position()).manhattanLength() < 12:
                mode = 'rotate'
            elif any((c-event.position()).manhattanLength() < 10 for c in corners):
                mode = 'scale'
        if mode == 'move':
            key = frame.pick((p.x(), p.y()), self._size(1000))
        if layers.selected == 'footer' and key in frame.footer:
            key = 'footer'
        layers.select(key)
        if key and frame.by_key[key].kind in ('text', 'plate', 'group'):
            self.drag = Drag(key, p, frame, (layers.composer.scope, layers.composer.index), mode,
                             (0., 0.) if mode == 'move' else (1., 0.))

    def mouseMoveEvent(self, event):
        if not self.drag:
            return super().mouseMoveEvent(event)
        self.drag.delta = self._gesture(event.position(), event.modifiers())
        if not self.timer.isActive():
            self.timer.start()
        self.update()
        event.accept()

    def _preview_motion(self):
        drag = self.drag
        if drag is None or not self.can_edit():
            self.cancel_move()
            return
        if self.job is not None:
            if not self.job.done():
                return
            if self.submitted and self.submitted[0] is drag and not self.job.cancelled() and self.job.exception() is None:
                self.draft = self.job.result()
                self.update()
            self.job = None
        if self.submitted == (drag, drag.delta):
            self.timer.stop()
            return
        doc = self.layers.gesture_document(drag.frame, drag.key, drag.mode, drag.delta)
        self.submitted = drag, drag.delta
        self.job = _drafts.submit(_render_draft, doc, self.layers.seconds, self._size(400))

    def mouseReleaseEvent(self, event):
        if not self.drag or event.button() != Qt.MouseButton.LeftButton:
            return super().mouseReleaseEvent(event)
        drag = self.drag
        delta = self._gesture(event.position(), event.modifiers())
        self.cancel_move()
        c = self.layers.composer
        if self.can_edit() and self.layers.frame is drag.frame and drag.scope == (c.scope, c.index):
            self.layers.commit_gesture(drag.frame, drag.key, drag.mode, delta)
        event.accept()

    def keyPressEvent(self, event):
        if self.drag and event.key() == Qt.Key.Key_Escape:
            self.cancel_move()
            event.accept()
        elif self.wants_arrow(event):
            dx, dy = self.arrows[event.key()]
            step = 10 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1
            self.layers.commit_move(self.layers.frame, self.layers.selected, dx * step, dy * step)
            event.accept()
        else:
            super().keyPressEvent(event)

    def wants_arrow(self, event):
        return (self.move_tool and self.can_nudge() and self.layers.frame and event.key() in self.arrows
                and event.modifiers() in (Qt.KeyboardModifier.NoModifier, Qt.KeyboardModifier.ShiftModifier)
                and self.layers.selected in (*self.layers.frame.order, 'footer')
                and self.layers.selected not in self.layers.frame.hidden and self.layers.at_playhead
                and self.layers.composer.look_tabs.currentWidget() is self.layers)

    def pending_wording(self):
        if self.word_editor and self.word_editor.toPlainText() != self.word_context[-1]:
            return [(self.word_editor, self.word_editor.toPlainText())]
        return []

    def finish_wording(self, *, cancel=False):
        edit = self.word_editor
        if edit is None:
            return True
        panel, document, scope, key, original = self.word_context
        current = (panel is self.layers and document is panel.composer.document and
                   scope == (panel.composer.scope, panel.composer.index))
        wording = edit.toPlainText()
        if current and not cancel:
            try:
                validate_text(wording)
            except ValueError as exc:
                panel.composer.failed.emit(str(exc))
                edit.setFocus()
                return False
        self.word_editor = self.word_context = None
        edit.hide()
        edit.deleteLater()
        if current and not cancel and wording != original:
            panel.composer.change_object_parameter(key, f'{key}.content', wording)
        self.wording_changed.emit()
        return True

    def edit_at(self, position):
        if not self.can_edit():
            return
        panel = self.layers
        point = self._point(position)
        key = panel.frame.pick((point.x(), point.y()), self._size(1000))
        panel.composer.look_tabs.setCurrentWidget(panel)
        panel.select(key)
        if not key or panel.frame.by_key[key].kind != 'text':
            return
        self.finish_wording()
        text = panel.frame.modules[key]['content']
        box = self._box(key)
        if not box:
            return
        self.word_context = (panel, panel.composer.document, (panel.composer.scope, panel.composer.index), key, text)
        edit = self.word_editor = CanvasWording(self)
        edit.setAccessibleName('Layer wording on canvas')
        edit.setToolTip('Enter to apply. Shift+Enter for a new line. Escape to cancel.')
        edit.setPlainText(text)
        edit.textChanged.connect(self.wording_changed)
        width = min(self.width(), max(170, round(box.width())+12))
        height = min(self.height(), max(40, edit.fontMetrics().lineSpacing()*(text.count('\n')+1)+16))
        edit.setGeometry(max(0, min(self.width()-width, round(box.center().x()-width/2))),
                         max(0, min(self.height()-height, round(box.center().y()-height/2))), width, height)
        edit.show()
        edit.setFocus()
        edit.selectAll()

    def mouseDoubleClickEvent(self, event):
        if self.move_tool and event.button() == Qt.MouseButton.LeftButton:
            self.cancel_move()
            self.edit_at(event.position())
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event):
        if self.drag:
            self.cancel_move()
        super().wheelEvent(event)

    def hideEvent(self, event):
        self.cancel_move()
        super().hideEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        layers = self.layers
        if not (self.move_tool and layers and layers.selected and self.packet and self.can_edit()
                and layers.composer.look_tabs.currentWidget() is layers):
            return
        frame = layers.frame
        rect = self.target_rect()
        box = self._box(layers.selected)
        if not box or layers.selected in frame.hidden:
            return
        painter = QPainter(self)
        painter.setClipRect(rect)
        if self.draft:
            (w, h), raw = self.draft
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.drawImage(rect, QImage(raw, w, h, w * 3, QImage.Format.Format_RGB888))
        move = self.drag.delta if self.drag and self.drag.mode == 'move' else (0., 0.)
        box.translate(move[0] * rect.width()/self.canvas_size[0], move[1] * rect.height()/self.canvas_size[1])
        if frame.by_key[layers.selected].kind == 'plate':
            scale, angle = self.drag.delta if self.drag and self.drag.mode != 'move' else (1., 0.)
            corners, top, rotate = self._plate_handles(frame, layers.selected, scale, angle, move)
            painter.setPen(QPen(QColor(238, 241, 237), 1, Qt.PenStyle.DashLine))
            painter.drawPolygon(QPolygonF(corners))
            painter.drawLine(top, rotate)
            painter.setBrush(QColor(238, 241, 237))
            painter.setPen(QColor(32, 34, 35))
            for corner in corners:
                painter.drawRect(QRectF(corner.x()-3, corner.y()-3, 6, 6))
            painter.drawEllipse(rotate, 4., 4.)
        else:
            painter.setPen(QPen(QColor(32, 34, 35, 180), 2))
            painter.drawRect(box)
            painter.setPen(QPen(QColor(238, 241, 237), 1, Qt.PenStyle.DashLine))
            painter.drawRect(box)
        if self.drag:
            x, y = self.drag.guides
            painter.setPen(QPen(QColor(160, 220, 165), 1))
            if x is not None:
                px = rect.left() + x*rect.width()/self.canvas_size[0]
                painter.drawLine(QPointF(px, rect.top()), QPointF(px, rect.bottom()))
            if y is not None:
                py = rect.top() + y*rect.height()/self.canvas_size[1]
                painter.drawLine(QPointF(rect.left(), py), QPointF(rect.right(), py))
