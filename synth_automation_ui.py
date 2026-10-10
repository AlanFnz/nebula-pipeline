"""Compact, draft-first gesture editor and keyboard-accessible event list."""
from __future__ import annotations
import copy
import math
import uuid

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QAction, QKeySequence, QPainter, QPainterPath, QColor, QPen
from PySide6.QtWidgets import (QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QFormLayout, QPushButton, QDialogButtonBox, QCheckBox, QListWidget, QMenu)
from studio_widgets import ComboBox, DoubleSpinBox, configure_parameter_spin
from studio_theme import COLORS
from synth_automation import TARGETS, STAGES, target_parameter, absolute_event, envelope, normalize_automations
from synth_effects import EFFECTS
from synth_instances import base_id, base_path, document_instance_ids
from synth_effects import EFFECT_BY_ID
from synth_composition import section_placements


def target_label(path):
    module = path.split('.')[0]
    if base_id(module) != module:
        return EFFECT_BY_ID[module].label + ' / ' + target_parameter(path).label
    effect = next(e for e in EFFECTS if path in e.paths)
    return effect.label + ' / ' + target_parameter(path).label


def occurrences(document):
    """Lane identities map each repeated occurrence to its one authored event."""
    result = []
    for index, start, _end, repetition in section_placements(document):
        section = document['sections'][index]
        for loop in range(section['loops']):
            origin = start + loop * section['duration']
            for event in section.get('automations', ()):
                result.append((section['id'], event['id'], origin,
                               absolute_event(event, section['duration'], origin)))
    return result


class CurvePreview(QWidget):
    def __init__(self):
        super().__init__(); self.gesture = None
        self.setFixedHeight(64); self.setMinimumWidth(0)
        self.setAccessibleName('Automation curve preview')

    def paintEvent(self, _event):
        painter = QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor(COLORS['border'])); painter.drawLine(8, self.height()-8, self.width()-8, self.height()-8)
        if not self.gesture: return
        e = dict(self.gesture, start=0, enabled=True)
        total = sum(e[k] for k in STAGES[1:])
        if total <= 0: return
        path = QPainterPath(QPointF(8, self.height()-8))
        for i in range(101):
            x = 8 + i / 100 * (self.width()-16)
            y = self.height()-8 - envelope(e, total*i/100) * (self.height()-16)
            path.lineTo(x, y)
        painter.setPen(QPen(QColor(COLORS['warning']), 2)); painter.drawPath(path)


class AutomationEditor(QDialog):
    def __init__(self, composer, path=None, section_id=None, event_id=None):
        super().__init__(composer)
        self.composer = composer; self.original_section = section_id; self.original_id = event_id
        self.original = None
        if event_id:
            section = next(s for s in composer.document['sections'] if s['id'] == section_id)
            self.original = copy.deepcopy(next(e for e in section['automations'] if e['id'] == event_id))
            path = self.original['path']
        self.identifier = event_id or 'gesture-' + uuid.uuid4().hex
        self.setWindowTitle('Edit automation' if event_id else 'Animate parameter')
        self.setMinimumWidth(320); self.resize(420, 480)
        layout = QVBoxLayout(self)
        hint = QLabel('Adds a temporary change to the base value, then returns to the moving base. Clip loops repeat this gesture; editing changes every repetition.')
        hint.setWordWrap(True); layout.addWidget(hint)
        form = QFormLayout(); form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow); layout.addLayout(form)
        self.target = ComboBox()
        targets = set(TARGETS)
        for identifier in document_instance_ids(composer.document):
            targets.update(identifier + '.' + p.split('.')[1] for p in TARGETS if p.split('.')[0] == base_id(identifier))
        for item in sorted(targets): self.target.addItem(target_label(item), item)
        self.target.setCurrentIndex(max(0, self.target.findData(path)))
        self.target.setEnabled(path is None)
        self.target.setAccessibleName('Automation target'); form.addRow('Parameter', self.target)
        self.section = ComboBox()
        for index, item in enumerate(composer.document['sections']):
            name = composer.document['phrases'][item['phrase']]['name']
            self.section.addItem(f"Clip {index+1} · {name}", item['id'])
        chosen = section_id or composer.automation_section_id()
        self.section.setCurrentIndex(max(0, self.section.findData(chosen)))
        self.section.setAccessibleName('Automation clip'); form.addRow('Clip', self.section)
        self.times = {}
        for key, label in zip(STAGES, ('Start', 'Rise', 'Hold', 'Recover')):
            control = DoubleSpinBox(); control.setDecimals(12); control.setRange(0, 300); control.setSuffix(' s')
            control.setSingleStep(1/composer.document['fps']); control.setKeyboardTracking(False)
            control.setAccessibleName('Automation ' + label); self.times[key] = control
            form.addRow(label, control); control.valueChanged.connect(self.update_curve)
        self.amount = DoubleSpinBox(); self.amount.setAccessibleName('Automation change amount'); form.addRow('Change amount', self.amount)
        self.easing = ComboBox(); self.easing.addItem('Smooth', 'smooth'); self.easing.addItem('Linear', 'linear')
        self.easing.setAccessibleName('Automation easing'); form.addRow('Easing', self.easing)
        self.enabled = QCheckBox('Enabled'); self.enabled.setChecked(True); form.addRow('', self.enabled)
        self.quick = QPushButton('Quick pull: short rise / long recovery'); layout.addWidget(self.quick)
        self.quick.clicked.connect(self.quick_pull)
        self.curve = CurvePreview(); layout.addWidget(self.curve)
        self.total = QLabel(); self.total.setWordWrap(True); layout.addWidget(self.total)
        self.notice = QLabel(); self.notice.setWordWrap(True); layout.addWidget(self.notice)
        self.error = QLabel(); self.error.setWordWrap(True); self.error.setStyleSheet(f"color: {COLORS['destructive']}"); layout.addWidget(self.error)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.apply)
        self.buttons.rejected.connect(self.reject); layout.addWidget(self.buttons)
        self.target.currentIndexChanged.connect(self.target_changed)
        self.section.currentIndexChanged.connect(self.section_changed)
        self.easing.currentIndexChanged.connect(self.update_curve)
        self.configure_amount(); self.section_changed()
        if self.original:
            duration = self.current_section()['duration']
            for key in STAGES: self.times[key].setValue(self.original[key+'_fraction']*duration)
            self.amount.setValue(self.original['amount']); self.enabled.setChecked(self.original['enabled'])
            self.easing.setCurrentIndex(self.easing.findData(self.original['easing']))
        self.update_curve()

    def current_section(self):
        return next(s for s in self.composer.document['sections'] if s['id'] == self.section.currentData())

    def configure_amount(self):
        spec = target_parameter(self.target.currentData()); configure_parameter_spin(self.amount, spec)
        span = spec.maximum-spec.minimum; self.amount.setRange(-span, span)
        self.amount.setValue(min(span, max(spec.step, span*(.15 if base_path(self.target.currentData()) == "tape.pull" else .3))))

    def section_changed(self):
        section = self.current_section(); duration = section['duration']
        for control in self.times.values(): control.setMaximum(duration)
        playhead = self.composer.playhead_seconds()
        origins = [start + loop*duration for index, start, end, rep in section_placements(self.composer.document)
                   if self.composer.document['sections'][index]['id'] == section['id']
                   for loop in range(section['loops']) if start+loop*duration <= playhead < start+(loop+1)*duration]
        if not origins:
            # At the final section endpoint propose a short gesture just inside
            # it, rather than resetting the artist's requested start to zero.
            endings = [end for index, start, end, rep in section_placements(self.composer.document)
                       if self.composer.document['sections'][index]['id'] == section['id'] and math.isclose(end, playhead, abs_tol=1e-12)]
            if endings: origins = [endings[-1]-duration]
        proposed = max(0., playhead - origins[0]) if origins else 0.
        start = min(proposed, max(0., duration-1/self.composer.document['fps']))
        self.times['start'].setValue(start); self.quick_pull()
        self._start_adjusted = start != proposed
        self.update_notice()

    def target_changed(self):
        self.configure_amount(); self.update_notice()

    def update_notice(self):
        if not hasattr(self, 'notice'): return
        section = self.current_section()
        start = self.times['start'].value()
        placements = [origin + loop*section['duration'] for index, origin, end, rep in section_placements(self.composer.document)
                      if self.composer.document['sections'][index]['id'] == section['id'] for loop in range(section['loops'])]
        playhead = self.composer.playhead_seconds()
        origin = next((origin for origin in placements if origin <= playhead < origin+section['duration']), placements[0])
        from synth_sequence import resolve_sequence_frame
        base = resolve_sequence_frame(self.composer.compiled, origin+start)[-1]
        module = self.target.currentData().split('.')[0]
        message = 'Start moved inside the clip to leave room for a gesture.' if getattr(self, '_start_adjusted', False) else ''
        if not any(m['id'] == module and m['enabled'] for m in base['modules']):
            message += ' This effect is inactive at the gesture start in the chosen clip. Automation retains its activation and bypass settings; enable or resume it to see the gesture.'
        self.notice.setText(message.strip())

    def quick_pull(self):
        remaining = max(0, self.current_section()['duration']-self.times['start'].value())
        total = min(1., remaining)
        self.times['attack'].setValue(total*.15); self.times['hold'].setValue(0); self.times['recovery'].setValue(total*.85)
        self.update_curve()

    def draft(self):
        duration = self.current_section()['duration']
        event = dict(id=self.identifier, path=self.target.currentData(), amount=self.amount.value(),
                     easing=self.easing.currentData(), enabled=self.enabled.isChecked())
        for key, control in self.times.items():
            value = control.value()/duration
            if self.original and self.section.currentData() == self.original_section and math.isclose(value, self.original[key+'_fraction'], abs_tol=1e-12):
                value = self.original[key+'_fraction']
            event[key+'_fraction'] = value
        return event

    def update_curve(self, *_args):
        if not hasattr(self, 'curve'): return
        event = self.draft(); self.curve.gesture = absolute_event(event, self.current_section()['duration']); self.curve.update()
        total = sum(control.value() for key, control in self.times.items() if key != 'start')
        self.total.setText(f'Duration {total:.2f}s · ends at {self.times["start"].value()+total:.2f}s in this clip')
        self.update_notice()

    def apply(self):
        try:
            self.composer.save_automation(self.section.currentData(), self.draft(), self.original_section, self.original_id)
        except ValueError as exc:
            self.error.setText(str(exc)); return
        self.accept()


class AutomationList(QDialog):
    def __init__(self, composer, path=None):
        super().__init__(composer); self.composer = composer; self.path = path; self.records = []
        self.setWindowTitle('Automations'); self.resize(500, 310)
        layout = QVBoxLayout(self)
        hint = QLabel('Events belong to clips and repeat with their loops. Base values and presets remain editable.'); hint.setWordWrap(True); layout.addWidget(hint)
        self.list = QListWidget(); self.list.setAccessibleName('Clip automation events'); layout.addWidget(self.list)
        row = QHBoxLayout(); layout.addLayout(row)
        self.add = QPushButton('Add…'); self.edit = QPushButton('Edit…'); self.toggle = QPushButton('Enable / Disable'); self.remove = QPushButton('Remove')
        for button in (self.add, self.edit, self.toggle, self.remove): row.addWidget(button)
        self.add.clicked.connect(lambda: composer.open_automation(self.path))
        self.edit.clicked.connect(self.edit_selected); self.list.itemDoubleClicked.connect(self.edit_selected)
        self.toggle.clicked.connect(lambda: self.change('toggle')); self.remove.clicked.connect(lambda: self.change('remove'))
        self.error = QLabel(); self.error.setWordWrap(True); layout.addWidget(self.error)
        self.close_button = QDialogButtonBox(QDialogButtonBox.StandardButton.Close); self.close_button.rejected.connect(self.reject); layout.addWidget(self.close_button)
        composer.changed.connect(self.refresh); self.list.currentRowChanged.connect(self.selection_changed); self.refresh()

    def refresh(self, *_args):
        previous = self.list.currentRow(); self.list.clear(); self.records = []
        for index, section in enumerate(self.composer.document['sections']):
            for event in section.get('automations', ()):
                if self.path and event['path'] != self.path: continue
                self.records.append((section['id'], event['id']))
                timing = absolute_event(event, section['duration'])
                end = sum(timing[k] for k in STAGES)
                self.list.addItem(f"Clip {index+1} · {target_label(event['path'])} · {timing['start']:.2f}–{end:.2f}s · {'Enabled' if event['enabled'] else 'Disabled'}")
        self.list.setCurrentRow(min(max(0, previous), len(self.records)-1)); self.selection_changed()

    def selection_changed(self, *_args):
        for button in (self.edit, self.toggle, self.remove): button.setEnabled(self.list.currentRow() >= 0)

    def edit_selected(self, *_args):
        row = self.list.currentRow()
        if row >= 0: self.composer.open_automation(section_id=self.records[row][0], event_id=self.records[row][1])

    def change(self, operation):
        row = self.list.currentRow()
        if row < 0: return
        try: self.composer.change_automation(*self.records[row], operation)
        except ValueError as exc: self.error.setText(str(exc))


class AutomationLane(QWidget):
    """Shared narrow lane; overlapping targets have explicit menu access."""
    def __init__(self, timeline):
        super().__init__(timeline); self.timeline = timeline; self.drag = None; self.selected = None; self.menu = None
        self.setMouseTracking(True); self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.duplicate_action = QAction('Duplicate automation', self)
        self.duplicate_action.setShortcut(QKeySequence('Ctrl+D'))
        self.duplicate_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        self.duplicate_action.triggered.connect(self.duplicate_selected)
        self.addAction(self.duplicate_action)
        self.setAccessibleName('Automation lane'); self.setAccessibleDescription('Select a gesture and press Command-D to duplicate. Use the Automations button to edit with the keyboard. Drag a gesture to move it; Escape cancels. Repeated gestures edit all repetitions.')

    def duplicate_selected(self):
        if self.selected and self.drag is None:
            self.timeline.automationRequested.emit(*self.selected, 'duplicate')

    def rectangles(self):
        if not self.timeline.document: return []
        scale = self.timeline.pixels_per_second(); result = []
        for section_id, event_id, origin, event in occurrences(self.timeline.document):
            if self.drag and (section_id, event_id) == self.drag['key']:
                event = dict(event, start=origin + self.drag['fraction'] * self.drag['duration'])
            duration = sum(event[k] for k in STAGES[1:])
            result.append((QRectF(event['start']*scale, 2, max(5, duration*scale), self.height()-4), section_id, event_id, origin, event))
        return result

    def hits(self, position): return [item for item in self.rectangles() if item[0].contains(position)]

    def paintEvent(self, _event):
        painter = QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(COLORS['panel']))
        for rect, sid, eid, origin, event in self.rectangles():
            selected = self.selected == (sid,eid)
            color = QColor(COLORS['warning'] if event['enabled'] else COLORS['disabled'])
            painter.setPen(QPen(color, 2 if selected else 1)); painter.setBrush(QColor(COLORS['raised'] if selected else COLORS['panel']))
            painter.drawRoundedRect(rect, 2, 2)
            curve = QPainterPath(QPointF(rect.left(), rect.bottom()-2))
            length = sum(event[k] for k in STAGES[1:])
            for i in range(41):
                curve.lineTo(rect.left()+rect.width()*i/40, rect.bottom()-2-envelope(dict(event, enabled=True), event['start']+length*i/40)*(rect.height()-4))
            painter.drawPath(curve)
        painter.setPen(QPen(QColor(COLORS['cursor']), 1)); x = self.timeline.time*self.timeline.pixels_per_second(); painter.drawLine(QPointF(x,0), QPointF(x,self.height()))

    def open_menu(self, hits, global_position):
        if self.menu: self.menu.deleteLater()
        self.menu = QMenu(self)
        for _rect, sid, eid, _origin, event in hits:
            submenu = self.menu.addMenu(target_label(event['path']))
            shortcut = self.duplicate_action.shortcut().toString(QKeySequence.SequenceFormat.NativeText)
            for label, action in (('Edit…', 'edit'), ('Duplicate\t' + shortcut, 'duplicate'), ('Disable' if event['enabled'] else 'Enable', 'toggle'), ('Remove', 'remove')):
                item = submenu.addAction(label); item.triggered.connect(lambda checked=False, sid=sid,eid=eid,action=action: self.timeline.automationRequested.emit(sid,eid,action))
        self.menu.popup(global_position)

    def mousePressEvent(self, event):
        hits = self.hits(event.position())
        if not hits:
            self.selected = None; self.setFocus(); self.update(); return
        if event.button() == Qt.MouseButton.RightButton or len(hits)>1:
            if len(hits) == 1: self.selected = hits[0][1:3]
            self.setFocus(); self.update()
            self.open_menu(hits, event.globalPosition().toPoint()); return
        if event.button() != Qt.MouseButton.LeftButton: return
        _rect, sid, eid, origin, absolute = hits[0]; self.selected=(sid,eid)
        section = next(s for s in self.timeline.document['sections'] if s['id']==sid)
        authored = next(e for e in section['automations'] if e['id']==eid)
        self.drag = dict(key=(sid,eid), press=event.position().x(), start=authored['start_fraction'], fraction=authored['start_fraction'],
                         duration=section['duration'], length=sum(authored[k+'_fraction'] for k in STAGES[1:]))
        self.setFocus(); self.update()

    def mouseMoveEvent(self, event):
        if self.drag:
            delta=(event.position().x()-self.drag['press'])/self.timeline.pixels_per_second()/self.drag['duration']
            self.drag['fraction']=max(0, min(1-self.drag['length'], self.drag['start']+delta)); self.update(); return
        hits=self.hits(event.position())
        self.setCursor(Qt.CursorShape.OpenHandCursor if hits else Qt.CursorShape.ArrowCursor)
        self.setToolTip('\n'.join(f"{target_label(e['path'])} · {e['start']:.2f}–{sum(e[k] for k in STAGES):.2f}s · {sid} · all repetitions share this event" for _,sid,eid,origin,e in hits))

    def mouseReleaseEvent(self, event):
        if not self.drag: return
        drag=self.drag; self.drag=None; self.update()
        if drag['fraction'] != drag['start']:
            self.timeline.automationMoveRequested.emit(*drag['key'], drag['fraction'])

    def mouseDoubleClickEvent(self, event):
        self.drag=None; hits=self.hits(event.position())
        if len(hits)==1: self.timeline.automationRequested.emit(hits[0][1],hits[0][2],'edit')
        elif hits: self.open_menu(hits,event.globalPosition().toPoint())

    def keyPressEvent(self, event):
        if event.key()==Qt.Key.Key_Escape: self.drag=None; self.update(); event.accept(); return
        if self.selected and event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter): self.timeline.automationRequested.emit(*self.selected,'edit'); return
        super().keyPressEvent(event)

    def hideEvent(self, event): self.drag=None; super().hideEvent(event)
