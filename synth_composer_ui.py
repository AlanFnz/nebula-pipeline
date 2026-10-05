"""Native composition controls: sections and a small set of musical macros."""
from __future__ import annotations

import copy
import math

from PySide6.QtCore import Qt, QRectF, QPoint, QSignalBlocker, Signal, QSize, QTimer
from PySide6.QtGui import QAction, QColor, QPainter, QPen, QCursor, QKeySequence
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel,
    QPushButton, QCheckBox, QTabWidget, QSizePolicy, QMenu, QInputDialog, QAbstractScrollArea, QApplication, QScrollArea, QFrame, QStackedWidget,
)
from studio_widgets import ComboBox as QComboBox, DoubleSpinBox as QDoubleSpinBox, SpinBox as QSpinBox, Slider as QSlider

from synth import SHAPES
from studio_theme import COLORS
from synth_composition import MACROS, compile_composition, default_geometry, effective_geometry, neutral_macros, normalize_composition, proportional_section_durations, section_placements, section_ranges, vary_composition
from synth_effects_ui import EffectsPanel
from synth_shared_timing import edit_shared_timing, restore_shared_timing, without_timing
from synth_master import normalize_master
from synth_master_ui import MasterPanel
from synth_subject import select_subject, restore_subject
from synth_subject_ui import SubjectPanel
from synth_video_ui import VideoSourcePanel
from synth_effects import EFFECTS
from synth_video import VIDEO_EFFECTS, apply_treatment


class SectionTimeline(QWidget):
    LANE_HEIGHT = 62
    BLOCK_TOP = 5
    BLOCK_HEIGHT = 46
    BLOCK_BOTTOM = BLOCK_TOP + BLOCK_HEIGHT
    READOUT_TOP = BLOCK_BOTTOM + 1

    selected = Signal(int)
    selectionChanged = Signal()
    loopRequested = Signal(object, int)
    seekRequested = Signal(float)
    durationRequested = Signal(str, float)
    stretchRequested = Signal(object, float)
    reorderRequested = Signal(object, object)
    duplicateRequested = Signal(object)
    automationVisibilityChanged = Signal(bool)
    automationRequested = Signal(str, str, str)
    automationMoveRequested = Signal(str, str, float)

    def __init__(self):
        super().__init__()
        self.document = None
        self.index = 0
        self.selected_ids = set()
        self.editing_section_id = None
        self.selection_anchor = None
        self.context_menu = None
        self.time = 0
        self._hover_edge = None
        self._resize = None
        self._reorder = None
        self._preview_document = None
        self._resize_scroll_timer = QTimer(self)
        self._resize_scroll_timer.setInterval(30)
        self._resize_scroll_timer.timeout.connect(self._auto_scroll_resize)
        self._reorder_scroll_timer = QTimer(self)
        self._reorder_scroll_timer.setInterval(30)
        self._reorder_scroll_timer.timeout.connect(self._auto_scroll_reorder)
        self.setFixedHeight(self.LANE_HEIGHT)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName('Section timeline')
        self.duplicate_action = QAction('Duplicate selected sections', self)
        self.duplicate_action.setShortcut(QKeySequence('Ctrl+D'))
        self.duplicate_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        self.duplicate_action.triggered.connect(self.duplicate_selected)
        self.addAction(self.duplicate_action)
        from synth_automation_ui import AutomationLane
        self.automation_lane = AutomationLane(self); self.automation_lane.hide()

    def set_document(self, document, index=0, reset_selection=False):
        if self._resize is not None: self._finish_resize(False)
        if self._reorder is not None: self._finish_reorder(False)
        self.automation_lane.drag = None
        old_ids = set(self.selected_ids)
        self.document = document
        if self.automation_lane.selected not in {
                (section['id'], event['id']) for section in document['sections']
                for event in section.get('automations', ())}:
            self.automation_lane.selected = None
        self.index = index
        ids = {section['id'] for section in document['sections']}
        if self.editing_section_id not in ids: self.editing_section_id = None
        current = document['sections'][index]['id']
        self.selected_ids.intersection_update(ids)
        if reset_selection or current not in self.selected_ids:
            self.selected_ids = {current}
            self.selection_anchor = current
        elif self.selection_anchor not in ids:
            self.selection_anchor = current
        self.setMinimumWidth(len(section_placements(document)) * 82)
        self._hover_edge = None
        has_events = any(section.get("automations") for section in document["sections"])
        self.setFixedHeight(self.LANE_HEIGHT + (30 if has_events else 0))
        self.automation_lane.setVisible(has_events)
        self.automationVisibilityChanged.emit(has_events)
        self.automation_lane.setGeometry(0, self.LANE_HEIGHT, self.width(), 30)
        self.automation_lane.update()
        self._update_accessible_description()
        self.update()
        if old_ids != self.selected_ids: self.selectionChanged.emit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.automation_lane.setGeometry(0, self.LANE_HEIGHT, self.width(), 30)

    def set_editing_section(self, section_id_or_none):
        """Mark the inspector's editing scope independently of arrangement selection."""
        self.editing_section_id = section_id_or_none
        self._update_accessible_description()
        self.update()

    def _update_accessible_description(self):
        if not self.document: return
        identities = [f"{index + 1}. {self.document['phrases'][section['phrase']]['name']} "
                      f"({section['id']}) · {section['duration']:.2f}s per play · "
                      f"{int(section.get('loops', 1))}× total plays"
                      for index, section in enumerate(self.document['sections'])]
        scope = next((identities[index] for index, section in enumerate(self.document['sections'])
                      if section['id'] == self.editing_section_id), 'Whole clip')
        self.setAccessibleDescription('Editing: ' + scope + '. Select sections and press Command-D to duplicate. Sections: ' + '; '.join(identities))

    def display_document(self):
        """The drag preview is private; only release requests a document edit."""
        return self._preview_document if self._preview_document is not None else self.document

    def pixels_per_second(self):
        if self._resize is not None: return self._resize['pixels_per_second']
        placements = section_placements(self.document) if self.document else []
        return self.width()/placements[-1][2] if placements else 1.

    def edge_at(self, position):
        if not self.document or not self.BLOCK_TOP <= position.y() <= self.BLOCK_BOTTOM: return None
        placements = section_placements(self.display_document())
        scale = self.pixels_per_second()
        candidates = []
        for occurrence, (_index, start, end, _repetition) in enumerate(placements):
            # Keep a draggable body even on short sections. A neighboring
            # section's handle must not consume the entire narrow block.
            left = min(6., (end - start) * scale / 4)
            right = min(6., (placements[occurrence + 1][2] - end) * scale / 4) if occurrence + 1 < len(placements) else 6.
            distance = position.x() - end * scale
            if -left <= distance <= right: candidates.append((abs(distance), occurrence))
        # A shared border always belongs to the view on its left.
        return min(candidates)[1] if candidates else None

    def _scroll_area(self):
        parent = self.parentWidget()
        while parent is not None:
            if isinstance(parent, QAbstractScrollArea): return parent
            parent = parent.parentWidget()
        return None

    def _begin_resize(self, occurrence, position):
        placements = section_placements(self.document)
        index, _start, end, _repetition = placements[occurrence]
        section = self.document['sections'][index]
        fps = self.document['fps']
        loops = int(section.get('loops', 1))
        occurrences = sum(item[0] == index for item in placements)
        total_factor = loops*occurrences
        # Earlier occurrences of the same section also ripple this edge. Divide
        # by their contribution so even a repeated view follows the pointer.
        edge_factor = loops*sum(item[0] == index for item in placements[:occurrence+1])
        original_frames = max(1, round(section['duration']*fps))
        other_frames = round(placements[-1][2]*fps)-original_frames*total_factor
        max_frames = min(math.floor(300*fps+1e-8),
                         math.floor((3600*fps-other_frames)/total_factor+1e-8))
        scroll = self._scroll_area()
        self._resize = dict(identifier=section['id'], index=index, occurrence=occurrence,
                            press_x=position.x(), pixels_per_second=self.width()/placements[-1][2],
                            original_frames=original_frames, frames=original_frames, fps=fps,
                            max_frames=max(1,max_frames), edge_factor=edge_factor,
                            original_edge=end*self.width()/placements[-1][2],
                            original_minimum=self.minimumWidth(), moved=False,
                            gutter=max(100,scroll.viewport().width()//4) if scroll else 0)
        if self._is_selection_edge(occurrence):
            identifiers = tuple(self.document['sections'][i]['id'] for i in self.selected_indices())
            original_durations = {item['id']: max(1, round(item['duration'] * fps)) / fps
                                  for item in self.document['sections'] if item['id'] in identifiers}
            edge_frames = sum(round(self.document['sections'][i]['duration'] * fps) *
                              int(self.document['sections'][i].get('loops', 1))
                              for i, *_ in placements[:occurrence+1]
                              if self.document['sections'][i]['id'] in identifiers)
            self._resize.update(identifiers=identifiers, factor=1., edge_frames=edge_frames,
                                original_durations=original_durations, durations=original_durations)
        self._preview_document = copy.deepcopy(self.document)
        self._preview_document['sections'][index]['duration'] = original_frames/fps
        self._grow_resize_canvas()
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        self.setCursor(Qt.CursorShape.SizeHorCursor)
        self.setToolTip((f'Drag to stretch {len(self._resize["identifiers"])} selected sections proportionally. '
                        if 'identifiers' in self._resize else 'Drag to retime this section and ripple later sections. ') +
                       'Release to apply; Escape to cancel.')
        self.update()

    def _is_selection_edge(self, occurrence):
        selected = self.selected_indices()
        return len(selected) > 1 and section_placements(self.document)[occurrence][0] == selected[-1]

    def _grow_resize_canvas(self):
        drag = self._resize
        if drag is None: return
        total = section_placements(self._preview_document)[-1][2]
        self.setMinimumWidth(max(drag['original_minimum'],
                                 math.ceil(total*drag['pixels_per_second'])+drag['gutter']))

    def _update_resize(self, x):
        drag = self._resize
        if drag is None: return
        if 'identifiers' in drag:
            factor = 1 + (x-drag['press_x']) / drag['pixels_per_second'] * drag['fps'] / drag['edge_frames']
            durations = proportional_section_durations(self.document, drag['identifiers'], factor)
            if durations == drag['durations']: return
            drag.update(factor=factor, durations=durations)
            for section in self._preview_document['sections']:
                if section['id'] in durations: section['duration'] = durations[section['id']]
            self._grow_resize_canvas()
            self.update()
            return
        delta = (x-drag['press_x'])/drag['pixels_per_second']/drag['edge_factor']
        frames = max(1,min(drag['max_frames'],round(drag['original_frames']+delta*drag['fps'])))
        if frames == drag['frames']: return
        drag['frames'] = frames
        self._preview_document['sections'][drag['index']]['duration'] = frames/drag['fps']
        self._grow_resize_canvas()
        self.update()

    def _auto_scroll_resize(self):
        drag = self._resize
        if drag is None or not drag['moved']: return
        scroll = self._scroll_area()
        if scroll is None: return
        point = scroll.viewport().mapFromGlobal(QCursor.pos())
        edge = 24
        distance = point.x()-edge if point.x() < edge else point.x()-(scroll.viewport().width()-edge) if point.x() > scroll.viewport().width()-edge else 0
        if not distance: return
        step = min(32,max(1,abs(distance)//2+1))*(1 if distance > 0 else -1)
        bar = scroll.horizontalScrollBar()
        before = bar.value()
        bar.setValue(before+step)
        if bar.value() != before:
            self._update_resize(self.mapFromGlobal(QCursor.pos()).x())

    def _finish_resize(self, commit):
        drag = self._resize
        if drag is None: return
        self._resize_scroll_timer.stop()
        self._resize = None
        self._preview_document = None
        self._hover_edge = None
        self.setMinimumWidth(drag['original_minimum'])
        self.unsetCursor()
        self.setToolTip('')
        self.update()
        if commit and 'identifiers' in drag:
            if drag['durations'] != drag['original_durations']:
                self.stretchRequested.emit(drag['identifiers'], drag['factor'])
        elif commit and drag['frames'] != drag['original_frames']:
            self.durationRequested.emit(drag['identifier'],drag['frames']/drag['fps'])

    def selected_indices(self):
        if not self.document: return []
        return [index for index, section in enumerate(self.document['sections'])
                if section['id'] in self.selected_ids]

    def _update_reorder(self, position):
        drag = self._reorder
        drag['position'] = position
        drag['valid'] = 0 <= position.y() < self.height()
        self.setCursor(Qt.CursorShape.ClosedHandCursor if drag['valid'] else Qt.CursorShape.ForbiddenCursor)
        if not drag['valid']:
            self.update(); return
        sections = self.document['sections']
        placements = section_placements(self.document)
        scale = self.pixels_per_second()
        # Repeated views share their original section. Only first-play
        # boundaries are legal insertion slots; repeats follow their owners.
        starts = {index: start * scale for index, start, _end, repeat in placements if repeat == 1}
        slots = [starts[index] for index in range(len(sections))] + [placements[-1][2] * scale]
        slot = min(range(len(slots)), key=lambda index: abs(slots[index] - position.x()))
        selected = set(drag['identifiers'])
        next_index = next((i for i in range(slot, len(sections)) if sections[i]['id'] not in selected), len(sections))
        before = sections[next_index]['id'] if next_index < len(sections) else None
        remaining = [section['id'] for section in sections if section['id'] not in selected]
        insertion = remaining.index(before) if before is not None else len(remaining)
        order = remaining[:insertion] + list(drag['identifiers']) + remaining[insertion:]
        drag.update(before=before, marker=slots[next_index],
                    changed=order != [section['id'] for section in sections])
        self.update()

    def _auto_scroll_reorder(self):
        drag = self._reorder
        if drag is None or not drag['active']: return
        scroll = self._scroll_area()
        if scroll is None: return
        position = scroll.viewport().mapFromGlobal(QCursor.pos())
        if not 0 <= position.y() < scroll.viewport().height(): return
        distance = position.x() - 24 if position.x() < 24 else position.x() - (scroll.viewport().width() - 24) if position.x() > scroll.viewport().width() - 24 else 0
        if not distance: return
        bar = scroll.horizontalScrollBar()
        step = min(32, max(1, abs(distance) // 2 + 1)) * (1 if distance > 0 else -1)
        bar.setValue(bar.value() + step)
        self._update_reorder(self.mapFromGlobal(QCursor.pos()))

    def _finish_reorder(self, commit):
        drag = self._reorder
        if drag is None: return
        self._reorder_scroll_timer.stop()
        self._reorder = None
        self._hover_edge = None
        self.unsetCursor(); self.setToolTip(''); self.update()
        if commit and drag['active'] and drag['valid'] and drag['changed']:
            self.reorderRequested.emit(drag['identifiers'], drag['before'])

    def section_at(self, position):
        occurrence = self.occurrence_at(position)
        return section_placements(self.document)[occurrence][0] if occurrence is not None else None

    def occurrence_at(self, position):
        return next((index for index, rect in enumerate(self.rectangles()) if rect.contains(position)), None)

    def select_at(self, index, modifiers=Qt.KeyboardModifier.NoModifier, context=False):
        identifier = self.document['sections'][index]['id']
        if context and index == self.index and identifier in self.selected_ids: return
        if context:
            if identifier not in self.selected_ids:
                self.selected_ids = {identifier}; self.selection_anchor = identifier
        elif modifiers & Qt.KeyboardModifier.ShiftModifier:
            anchor = next((i for i, section in enumerate(self.document['sections'])
                           if section['id'] == self.selection_anchor), self.index)
            self.selected_ids = {self.document['sections'][i]['id']
                                 for i in range(min(anchor, index), max(anchor, index) + 1)}
        elif modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
            if identifier in self.selected_ids and len(self.selected_ids) > 1:
                self.selected_ids.remove(identifier)
                index = self.selected_indices()[-1]
            else:
                self.selected_ids.add(identifier)
            self.selection_anchor = self.document['sections'][index]['id']
        else:
            self.selected_ids = {identifier}; self.selection_anchor = identifier
        self.index = index
        self.update()
        self.selected.emit(index)
        self.selectionChanged.emit()

    def set_time(self, time):
        self.time = time
        self.automation_lane.update()
        self.update()

    def rectangles(self):
        document = self.display_document()
        if not document:
            return []
        placements = section_placements(document)
        scale = self.pixels_per_second()
        return [QRectF(start*scale+2, self.BLOCK_TOP, max(1,(end-start)*scale-4), self.BLOCK_HEIGHT)
                for _index, start, end, _repetition in placements]

    def text_rectangles(self, rect):
        """Both text lines stay inside even a one-pixel section body."""
        padding = min(5., rect.width() / 2)
        width = max(0., rect.width() - 2 * padding)
        line_height = (rect.height() - 4) / 2
        return (QRectF(rect.left() + padding, rect.top() + 2, width, line_height),
                QRectF(rect.left() + padding, rect.top() + 2 + line_height, width, line_height))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        document = self.display_document()
        placements = section_placements(document) if document else []
        selected_indices = self.selected_indices()
        selection_end = selected_indices[-1] if len(selected_indices) > 1 else None
        for occurrence, ((index, _start, _end, repetition), rect) in enumerate(zip(placements, self.rectangles())):
            section = document["sections"][index]
            selected = section['id'] in self.selected_ids
            painter.save()
            if self._reorder and self._reorder['active'] and selected: painter.setOpacity(.45)
            editing = section['id'] == self.editing_section_id
            painter.setBrush(QColor(COLORS["selected"] if editing else COLORS["panel"]))
            painter.setPen(QPen(QColor(COLORS["accent"] if selected else COLORS["border"]), 1))
            painter.drawRect(rect)
            painter.save()
            painter.setClipRect(rect.adjusted(1, 1, -1, -1))
            title_rect, metadata_rect = self.text_rectangles(rect)
            number = f'{index + 1:02d}' + (f' / ↻{repetition}' if repetition > 1 else '')
            label = document["phrases"][section["phrase"]]["name"]
            label_font = self.font(); label_font.setPixelSize(11); painter.setFont(label_font)
            painter.setPen(QColor(COLORS["text"]))
            label = painter.fontMetrics().elidedText(f'{number} {label}', Qt.TextElideMode.ElideRight, int(title_rect.width()))
            painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label)
            small_font = self.font(); small_font.setPixelSize(10)
            painter.setFont(small_font); painter.setPen(QColor(COLORS["muted"]))
            loops = int(section.get('loops', 1))
            metadata = painter.fontMetrics().elidedText(f"{section['duration']:.2f}s ×{loops}",
                                                      Qt.TextElideMode.ElideRight, int(metadata_rect.width()))
            painter.drawText(metadata_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, metadata)
            painter.restore()
            if selected or occurrence == self._hover_edge:
                selection_edge = index == selection_end
                painter.setPen(QPen(QColor(COLORS['accent'] if occurrence == self._hover_edge or selection_edge else COLORS['muted']),
                                    4 if selection_edge else 2))
                edge = min(self.width()-2,round(_end*self.pixels_per_second()-3))
                painter.drawLine(edge, self.BLOCK_TOP + 12, edge, self.BLOCK_BOTTOM - 12)
            painter.restore()
        if self.document:
            x = max(1, min(self.width()-1,self.time*self.pixels_per_second()))
            painter.setPen(QPen(QColor(COLORS["cursor"]), 1))
            painter.drawLine(int(x), 2, int(x), self.BLOCK_BOTTOM + 2)
            painter.fillRect(QRectF(x - 3, 0, 6, 3), QColor(COLORS["cursor"]))
        if self._resize is not None:
            drag = self._resize
            painter.setPen(QPen(QColor(COLORS['cursor']),1,Qt.PenStyle.DashLine))
            painter.drawLine(round(drag['original_edge']), self.BLOCK_TOP,
                             round(drag['original_edge']), self.BLOCK_BOTTOM)
            font = self.font(); font.setPixelSize(10); painter.setFont(font)
            painter.setPen(QColor(COLORS['accent']))
            visible = self.visibleRegion().boundingRect()
            readout = f"{drag['frames']/drag['fps']:.2f}s per play · {drag['frames']/drag['original_frames']:.2f}× length · release to apply · Esc cancel"
            if 'identifiers' in drag:
                scale = sum(drag['durations'].values()) / sum(drag['original_durations'].values())
                total = placements[-1][2]
                readout = f"{len(drag['identifiers'])} sections · {scale:.2f}× length · {total:.2f}s timeline · release to apply · Esc cancel"
            readout = painter.fontMetrics().elidedText(readout, Qt.TextElideMode.ElideRight, max(0, visible.width() - 12))
            painter.drawText(QRectF(visible.left()+6,self.READOUT_TOP,max(0,visible.width()-12),self.height()-self.READOUT_TOP),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,readout)
        if self._reorder is not None and self._reorder['active']:
            drag = self._reorder
            visible = self.visibleRegion().boundingRect()
            count = len(drag['identifiers'])
            font = self.font(); font.setPixelSize(10); painter.setFont(font)
            color = QColor(COLORS['accent'] if drag['valid'] and drag['changed'] else COLORS['muted'])
            if drag['valid']:
                x = max(2, min(self.width() - 3, round(drag['marker'])))
                painter.setPen(QPen(color, 3)); painter.drawLine(x, 3, x, self.BLOCK_BOTTOM)
                painter.fillRect(QRectF(x - 4, 2, 9, 4), color)
                painter.fillRect(QRectF(x - 4, self.BLOCK_BOTTOM - 3, 9, 4), color)
            before = next((i + 1 for i, section in enumerate(document['sections']) if section['id'] == drag.get('before')), None)
            destination = f'before section {before:02d}' if before is not None else 'to the end'
            readout = (f'Move {count} section' + ('s' if count > 1 else '') + f' {destination} · repetitions follow · Esc cancels') if drag['valid'] else 'Move back over the timeline to drop · Esc cancels'
            if drag['valid'] and not drag['changed']: readout = 'Current order · Esc cancels'
            painter.setPen(color)
            readout = painter.fontMetrics().elidedText(readout, Qt.TextElideMode.ElideRight, max(0, visible.width() - 12))
            painter.drawText(QRectF(visible.left()+6,self.READOUT_TOP,max(0,visible.width()-12),self.height()-self.READOUT_TOP),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,readout)
            label = f'{count} sections' if count > 1 else document['phrases'][document['sections'][self.index]['phrase']]['name']
            width = min(200, max(70, painter.fontMetrics().horizontalAdvance(label) + 20))
            x = max(visible.left(), min(drag['position'].x() + 12, visible.right() - width))
            ghost = QRectF(x, self.BLOCK_TOP + 10, width, 26)
            painter.setOpacity(.9); painter.setPen(QPen(color, 1)); painter.setBrush(QColor(COLORS['selected']))
            painter.drawRoundedRect(ghost, 3, 3)
            painter.drawText(ghost.adjusted(8, 0, -8, 0), Qt.AlignmentFlag.AlignCenter,
                             painter.fontMetrics().elidedText(label, Qt.TextElideMode.ElideRight, width - 16))

    def mousePressEvent(self, event):
        if event.button() not in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton): return
        if self._resize is not None or self._reorder is not None: return
        edge = self.edge_at(event.position())
        if event.button() == Qt.MouseButton.LeftButton and event.modifiers() == Qt.KeyboardModifier.NoModifier and edge is not None:
            index, start, _end, _repetition = section_placements(self.document)[edge]
            self.select_at(index, context=self._is_selection_edge(edge))
            self.seekRequested.emit(start)
            self._begin_resize(edge,event.position())
            event.accept()
            return
        occurrence = self.occurrence_at(event.position())
        if occurrence is None: occurrence = edge
        if occurrence is None: return
        index, start, _end, _repetition = section_placements(self.document)[occurrence]
        can_drag = event.button() == Qt.MouseButton.LeftButton and event.modifiers() == Qt.KeyboardModifier.NoModifier
        preserve_selection = can_drag and self.document['sections'][index]['id'] in self.selected_ids
        self.select_at(index, event.modifiers(), context=event.button() == Qt.MouseButton.RightButton or preserve_selection)
        self.seekRequested.emit(start)
        if can_drag:
            self._reorder = dict(press=event.position(), start=start, active=False, valid=False, changed=False,
                                 identifiers=tuple(self.document['sections'][i]['id'] for i in self.selected_indices()))
            self.setFocus(Qt.FocusReason.MouseFocusReason)
        event.accept()

    def mouseReleaseEvent(self, event):
        if self._reorder is not None and event.button() == Qt.MouseButton.LeftButton:
            active = self._reorder['active']
            start = self._reorder['start']
            if active: self._update_reorder(event.position())
            self._finish_reorder(True)
            if not active:
                self.select_at(self.index)
                self.seekRequested.emit(start)
            event.accept(); return
        if self._resize is not None and event.button() == Qt.MouseButton.LeftButton:
            self._update_resize(event.position().x())
            self._finish_resize(True)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if self._reorder is not None and event.key() == Qt.Key.Key_Escape:
            self._finish_reorder(False)
            event.accept(); return
        if self._resize is not None and event.key() == Qt.Key.Key_Escape:
            self._finish_resize(False)
            event.accept()
            return
        if self.document and self._resize is None and self._reorder is None and event.matches(QKeySequence.StandardKey.SelectAll):
            self.selected_ids = {section['id'] for section in self.document['sections']}
            self.update(); self.selectionChanged.emit()
            event.accept(); return
        super().keyPressEvent(event)

    def duplicate_selected(self):
        if not self.document or self._resize is not None or self._reorder is not None: return
        self.duplicateRequested.emit(tuple(self.document['sections'][i]['id']
                                          for i in self.selected_indices()))

    def leaveEvent(self, event):
        if self._resize is None and self._reorder is None:
            self._hover_edge = None
            self.unsetCursor()
            self.update()
        super().leaveEvent(event)

    def hideEvent(self, event):
        if self._resize is not None: self._finish_resize(False)
        if self._reorder is not None: self._finish_reorder(False)
        super().hideEvent(event)

    def make_context_menu(self):
        identifiers = tuple(self.document['sections'][i]['id'] for i in self.selected_indices())
        menu = QMenu(self)
        menu.setTitle('Timeline sections')
        label = 'Loop' if len(identifiers) == 1 else f'Loop {len(identifiers)} selected sections'
        action = menu.addAction(label)
        action.setToolTip('Add one repetition to the selected section or sections.')
        action.triggered.connect(lambda: self.loopRequested.emit(identifiers, 0))
        counts = menu.addMenu('Repeat count')
        for count in (2, 3, 4, 8, 16, 32):
            action = counts.addAction(f'{count}× total plays')
            action.triggered.connect(lambda checked=False, count=count: self.loopRequested.emit(identifiers, count))
        custom = counts.addAction('Custom…')
        custom.triggered.connect(lambda: self.custom_loop_count(identifiers))
        menu.addSeparator()
        remove = menu.addAction('Remove loop')
        remove.triggered.connect(lambda: self.loopRequested.emit(identifiers, 1))
        for group in self.document.get('timeline_loops', []):
            if set(group['sections']) & set(identifiers) and set(group['sections']) != set(identifiers):
                action = menu.addAction(f"Remove sequence loop ({len(group['sections'])} sections)")
                members = tuple(group['sections'])
                action.triggered.connect(lambda checked=False, members=members: self.loopRequested.emit(members, 1))
        menu.addSeparator()
        menu.addAction(self.duplicate_action)
        return menu

    def custom_loop_count(self, identifiers):
        counts = [int(section.get('loops', 1)) for section in self.document['sections']
                  if section['id'] in identifiers]
        for group in self.document.get('timeline_loops', []):
            if set(group['sections']) == set(identifiers): counts = [group['loops']]
        count, accepted = QInputDialog.getInt(self, 'Timeline loop', 'Total plays (1 = once):',
                                             max(counts, default=1), 1, 32)
        if accepted: self.loopRequested.emit(identifiers, count)

    def contextMenuEvent(self, event):
        index = self.section_at(event.pos())
        if index is None: return
        self.select_at(index, context=True)
        if self.context_menu is not None: self.context_menu.deleteLater()
        self.context_menu = self.make_context_menu()
        self.context_menu.popup(event.globalPos())
        event.accept()

    def mouseMoveEvent(self, event):
        if self._reorder is not None:
            drag = self._reorder
            if not drag['active'] and (event.position() - drag['press']).manhattanLength() >= QApplication.startDragDistance():
                drag['active'] = True
                self._hover_edge = None
                self.setToolTip('')
                self._reorder_scroll_timer.start()
            if drag['active']: self._update_reorder(event.position())
            event.accept(); return
        if self._resize is not None:
            if abs(event.position().x()-self._resize['press_x']) >= 2:
                self._resize['moved'] = True
                if not self._resize_scroll_timer.isActive(): self._resize_scroll_timer.start()
            self._update_resize(event.position().x())
            event.accept()
            return
        edge = self.edge_at(event.position())
        if edge != self._hover_edge:
            self._hover_edge = edge
            self.update()
        self.setCursor(Qt.CursorShape.SizeHorCursor if edge is not None else Qt.CursorShape.ArrowCursor)
        if edge is not None:
            index = section_placements(self.document)[edge][0]
            duration = self.document['sections'][index]['duration']
            self.setToolTip((f'Drag to stretch {len(self.selected_ids)} selected sections proportionally · '
                            if self._is_selection_edge(edge) else f'Drag right edge to retime section {index+1} · {duration:.2f}s per play · ') +
                           'later sections ripple · Escape cancels')
            return
        placements = section_placements(self.document) if self.document else []
        for (index, _start, _end, repetition), rect in zip(placements, self.rectangles()):
            if rect.contains(event.position()):
                self.setCursor(Qt.CursorShape.OpenHandCursor)
                section = self.document["sections"][index]
                loops = int(section.get('loops', 1))
                self.setToolTip(f"{index + 1}. {self.document['phrases'][section['phrase']]['name']} · {section['duration']:.2f}s per play · {loops}× total plays · " +
                               (f'Sequence repetition {repetition} · ' if repetition > 1 else '') +
                               'drag body to reorder; drag the last selected edge to stretch the selection; Shift-click to select a range; Command-click to add sections; Command-A to select all; Command-D to duplicate; right-click for actions')
                return
        self.setToolTip('')


class MacroControl(QWidget):
    changed = Signal(float)
    locked = Signal(bool)

    def __init__(self, label, low, high, hint):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 2)
        row = QHBoxLayout()
        name = QLabel(label); name.setFixedWidth(88)
        row.addWidget(name)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setTracking(False)
        self.slider.setRange(round(low * 100), round(high * 100))
        row.addWidget(self.slider, 1)
        self.lock = QCheckBox("Keep")
        self.lock.setToolTip("Keep this control when generating a new take.")
        self.spin = QDoubleSpinBox()
        self.spin.setRange(low, high); self.spin.setSingleStep(.05); self.spin.setDecimals(2)
        self.spin.setSuffix(" ×"); self.spin.setFixedWidth(76); self.spin.setKeyboardTracking(False)
        row.addWidget(self.spin)
        row.addWidget(self.lock)
        layout.addLayout(row)
        self.setToolTip(hint)
        self.spin.valueChanged.connect(self._spin_changed)
        self.slider.valueChanged.connect(lambda value: self.spin.setValue(value / 100))
        self.lock.toggled.connect(self.locked.emit)

    def _spin_changed(self, value):
        with QSignalBlocker(self.slider):
            self.slider.setValue(round(value * 100))
        self.changed.emit(value)

    def set_value(self, value, locked):
        with QSignalBlocker(self.spin), QSignalBlocker(self.slider), QSignalBlocker(self.lock):
            self.spin.setValue(value); self.slider.setValue(round(value * 100)); self.lock.setChecked(locked)


class InspectorTabs(QTabWidget):
    """Pinned tabs with one bounded scroll area per content page.

    Public page lookup keeps returning the original inspector widget so existing
    navigation code does not need to know which pages have a scroll wrapper.
    """
    def __init__(self):
        super().__init__()
        self._scroll_pages = {}
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def addTab(self, page, label):
        if isinstance(page, EffectsPanel): return super().addTab(page, label)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(page); self._scroll_pages[page] = scroll
        return super().addTab(scroll, label)

    def widget(self, index):
        wrapper = super().widget(index)
        return wrapper.widget() if isinstance(wrapper, QScrollArea) else wrapper

    def currentWidget(self): return self.widget(self.currentIndex())
    def indexOf(self, page): return super().indexOf(self._scroll_pages.get(page, page))
    def setCurrentWidget(self, page): super().setCurrentWidget(self._scroll_pages.get(page, page))
    def sizeHint(self): return QSize(320, 420)
    def minimumSizeHint(self):
        page = super().currentWidget()
        content = page.minimumSizeHint() if page else QSize(0, 0)
        return QSize(min(320, content.width())+6, content.height()+self.tabBar().sizeHint().height()+6)
    def hasHeightForWidth(self): return False


class CompositionPanel(QWidget):
    changed = Signal(object, str)
    failed = Signal(str)
    sectionSelected = Signal(int)
    detailsRequested = Signal()
    relinkRequested = Signal()
    reset_context_changed = Signal(str)

    def __init__(self, document, index=0, scope=0):
        super().__init__()
        self.document = normalize_composition(document)
        self.index = min(index, len(document["sections"]) - 1)
        self.scope = scope
        self.updating = False
        self.playhead_seconds = lambda: 0.
        self.automation_dialogs = []
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(5)
        title = QLabel("02 / INSPECTOR"); title.setObjectName("sectionTitle")
        title_row = QHBoxLayout(); title_row.addWidget(title); title_row.addStretch(1)
        self.timeline_summary = QLabel(); self.timeline_summary.setObjectName('muted')
        self.timeline_summary.setToolTip('Total duration and section count for the whole timeline, including loops.')
        title_row.addWidget(self.timeline_summary); layout.addLayout(title_row)
        hint = QLabel("Combine effects. Arrange their changes in sections.")
        hint.setWordWrap(True); hint.setObjectName("muted"); hint.hide(); title.setToolTip(hint.text())

        self.workspace_actions = QWidget(); self.workspace_actions.setProperty('chrome', True)
        self.workspace_actions_layout = QHBoxLayout(self.workspace_actions)
        self.workspace_actions_layout.setContentsMargins(0, 0, 0, 0)
        self.workspace_actions_layout.addStretch(1)
        layout.addWidget(self.workspace_actions)
        self.timeline_controls = QWidget(); self.timeline_controls.setProperty('chrome', True)
        timeline_row = QHBoxLayout(self.timeline_controls); timeline_row.setContentsMargins(0, 0, 0, 0)
        self.fps_label = QLabel('Timeline FPS')
        self.fps = QSpinBox(); self.fps.setRange(1, 120); self.fps.setSuffix(" fps"); self.fps.setKeyboardTracking(False)
        self.fps.setAccessibleName('Timeline FPS')
        self.fps_label.setBuddy(self.fps)
        self.fps.setToolTip('Global frame rate for preview and export, across every section, regardless of editing scope. Lower it for a stepped cadence without slowing the action. Section durations round to the nearest frame. Source and effect cadence controls can hold individual parts longer.')
        self.fps_label.setToolTip(self.fps.toolTip())
        timeline_row.addWidget(self.fps_label); timeline_row.addWidget(self.fps); timeline_row.addStretch(1)
        self.arrangement_button = QPushButton('Arrange sections…'); self.arrangement_button.setCheckable(True)
        self.arrangement_button.setToolTip("Edit section durations, order and loops.")
        self.automations_button = QPushButton("Automations…")
        self.automations_button.setProperty("compact", True); self.automations_button.clicked.connect(lambda: self.open_automation_list())
        self.workspace_actions_layout.addWidget(self.automations_button)
        self.workspace_actions_layout.addWidget(self.arrangement_button); layout.addWidget(self.timeline_controls)
        self.content_stack = QStackedWidget(); layout.addWidget(self.content_stack, 1)
        self.arrangement_scroll = QScrollArea(); self.arrangement_scroll.setWidgetResizable(True)
        self.arrangement_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.arrangement_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        arrangement_host = QWidget(); arrangement_layout = QVBoxLayout(arrangement_host)
        arrangement_layout.setContentsMargins(0, 0, 0, 0)
        self.arrangement_scroll.setWidget(arrangement_host); self.content_stack.addWidget(self.arrangement_scroll)

        clip = QGroupBox("CLIP / TIMING")
        grid = QGridLayout(clip)
        self.duration = QDoubleSpinBox(); self.duration.setRange(.24, 3600); self.duration.setDecimals(2); self.duration.setSuffix(" s"); self.duration.setKeyboardTracking(False)
        grid.addWidget(QLabel("Total duration"), 0, 0)
        grid.addWidget(self.duration, 1, 0)
        self.duration.valueChanged.connect(self.resize_clip)
        self.fps.valueChanged.connect(self.change_fps)
        arrangement_layout.addWidget(clip)

        section_box = QGroupBox("SEQUENCE / ARRANGEMENT")
        section_layout = QVBoxLayout(section_box)
        self.section_combo = QComboBox(); self.section_combo.currentIndexChanged.connect(self.select_section)
        section_layout.addWidget(self.section_combo)
        row = QHBoxLayout()
        self.phrase = QComboBox()
        for key, phrase in self.document["phrases"].items():
            self.phrase.addItem(phrase["name"], key)
        self.phrase.currentIndexChanged.connect(self.change_phrase); row.addWidget(self.phrase, 1)
        self.section_duration = QDoubleSpinBox(); self.section_duration.setRange(1 / self.document["fps"], 300); self.section_duration.setDecimals(2); self.section_duration.setSuffix(" s"); self.section_duration.setFixedWidth(95); self.section_duration.setKeyboardTracking(False)
        self.resize_mode = 'effects'
        self.section_duration.setToolTip('Stretch this section and all its effects. The Resize menu below the timeline chooses whether imported video also changes speed.')
        self.section_duration.valueChanged.connect(self.resize_section); row.addWidget(self.section_duration)
        row.addWidget(QLabel('Loops'))
        self.section_loops = QSpinBox(); self.section_loops.setRange(1, 32); self.section_loops.setSuffix(" ×"); self.section_loops.setFixedWidth(68); self.section_loops.setKeyboardTracking(False)
        self.section_loops.setAccessibleName('Section loops')
        self.section_loops.setToolTip('Total plays of this section: 1 = once, 2 = twice. '
                                     'Repeats its edited event sequence; procedural motion/noise and imported footage keep running. '
                                     'Total duration uses section duration × loops.')
        self.section_loops.valueChanged.connect(self.resize_section_loops); row.addWidget(self.section_loops)
        section_layout.addLayout(row)
        row = QHBoxLayout()
        for label, callback in (("+ Add", self.add_section), ("Duplicate", self.duplicate_section), ("Remove", self.remove_section), ("←", lambda: self.move_section(-1)), ("→", lambda: self.move_section(1))):
            button = QPushButton(label); button.clicked.connect(callback); row.addWidget(button)
        section_layout.addLayout(row)
        arrangement_layout.addWidget(section_box); arrangement_layout.addStretch(1)

        shape = QWidget()
        shape_layout = QVBoxLayout(shape); shape_layout.setContentsMargins(0, 0, 0, 0); shape_layout.setSpacing(5)
        self.scope_combo = QComboBox(); self.scope_combo.addItems(["Whole clip", "Selected section"])
        self.scope_combo.currentIndexChanged.connect(self.change_scope); shape_layout.addWidget(self.scope_combo)
        self.timing_scope_label = QLabel('Editing: Whole clip · shared timing'); self.timing_scope_label.hide()
        shape_layout.addWidget(self.timing_scope_label)
        self.master_scope_label = QLabel('Editing: Whole clip · master adjustments'); self.master_scope_label.hide()
        shape_layout.addWidget(self.master_scope_label)
        self.source_scope_label = QLabel('Editing: Whole clip · source video'); self.source_scope_label.hide()
        shape_layout.addWidget(self.source_scope_label)
        self.look_tabs = InspectorTabs()
        self.effects_panel = EffectsPanel()
        # The composer owns the persistent scope selector for every page.
        self.effects_panel.scope_label.hide()
        self.effects_panel.edited.connect(self.change_effect)
        self.effects_panel.automation_requested.connect(self.parameter_automation)
        self.effects_panel.instance_requested.connect(self.add_effect_instance)
        self.effects_panel.timing_edited.connect(self.change_ink_timing)
        self.effects_panel.timing_reset.connect(self.reset_ink_timing)
        self.effects_panel.timing_selected.connect(self.show_timing_scope)
        self.effects_panel.navigation_changed.connect(self.emit_reset_context)
        self.effects_panel.object_requested.connect(lambda: self.look_tabs.setCurrentWidget(self.object_panel))
        self.look_tabs.addTab(self.effects_panel, "Effects")
        self.object_panel = SubjectPanel(); geometry_page = self.object_panel
        geometry_layout = self.object_panel.signal_layout
        self.object_panel.selected.connect(self.change_object)
        self.object_panel.restored.connect(self.restore_object)
        self.object_panel.parameter_changed.connect(self.change_object_parameter)
        self.object_panel.parameter_reset.connect(self.reset_object_parameter)
        self.object_panel.details_requested.connect(self.open_object_details)
        self.object_panel.position_changed.connect(self.change_geometry)
        self.object_panel.position_reset.connect(self.reset_object_position)
        treatment_page = QWidget(); treatment_layout = QVBoxLayout(treatment_page)
        self.look_tabs.addTab(geometry_page, "Object"); self.look_tabs.addTab(treatment_page, "Finishing")
        self.master_panel = MasterPanel()
        self.master_panel.edited.connect(self.change_master)
        self.master_panel.resetRequested.connect(self.reset_master)
        self.look_tabs.addTab(self.master_panel, 'Master')
        self.video_panel = VideoSourcePanel()
        self.video_panel.edited.connect(self.change_video)
        self.video_panel.relinkRequested.connect(self.relinkRequested.emit)
        self.video_panel.durationRequested.connect(self.resize_video_duration)
        self.video_panel.sourceModeRequested.connect(self.change_video_source_mode)
        self.video_panel.speedRequested.connect(self.change_video_speed)
        self.video_panel.treatmentRequested.connect(self.apply_video_treatment)
        self.look_tabs.addTab(self.video_panel, 'Source')
        self.look_tabs.currentChanged.connect(lambda _index: self.show_timing_scope(self.effects_panel.effect_id == 'ink_bloom' and self.effects_panel.parameter_tabs.currentIndex() == 1))
        self.look_tabs.currentChanged.connect(self.size_current_tab)
        self.look_tabs.currentChanged.connect(self.emit_reset_context)
        self.size_current_tab()
        treatment_hint = QLabel("Relative adjustments to the recipe. 1× keeps its original treatment; different recipes can look different at 1×.")
        treatment_hint.setWordWrap(True); treatment_hint.setObjectName("muted"); treatment_layout.addWidget(treatment_hint)
        shape_layout.addWidget(self.look_tabs)
        self.geometry_shape = QComboBox()
        self.geometry_shape.currentIndexChanged.connect(self.change_shape)
        geometry_layout.addWidget(self.geometry_shape)
        self.macro_controls = {}
        for key, (label, low, high, tip) in MACROS.items():
            control = MacroControl(label, low, high, tip)
            control.changed.connect(lambda value, key=key: self.change_macro(key, value))
            control.locked.connect(lambda value, key=key: self.lock_macro(key, value))
            (geometry_layout if key == "width" else treatment_layout).addWidget(control)
            self.macro_controls[key] = control
        self.geometry_controls = {}; self.geometry_rows = {}
        for key, label, low, high, step, suffix in (("height", "Height", .25, 2., .05, " ×"), ("diameter", "Diameter", 5., 150., 1., " %"), ("sides", "Sides", 3, 32, 1, ""), ("rotation", "Rotation", -180., 180., 1., "°")):
            row_widget = QWidget(); row = QHBoxLayout(row_widget); row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(QLabel(label)); row.addStretch(1)
            control = QSpinBox() if key == "sides" else QDoubleSpinBox()
            control.setRange(low, high); control.setSingleStep(step); control.setSuffix(suffix); control.setKeyboardTracking(False)
            control.setFixedWidth(110)
            if key != "sides": control.setDecimals(2 if key == "height" else 1)
            control.valueChanged.connect(lambda value, key=key: self.change_geometry(key, value / 100 if key == "diameter" else value))
            row.addWidget(control); geometry_layout.addWidget(row_widget)
            self.geometry_controls[key] = control; self.geometry_rows[key] = row_widget
        self.geometry_hint = QLabel(); self.geometry_hint.setWordWrap(True); self.geometry_hint.setObjectName("muted")
        geometry_layout.addWidget(self.geometry_hint); geometry_layout.addStretch(1)
        treatment_layout.addStretch(1)
        self.take_label = QLabel(); self.take_label.setObjectName("muted"); shape_layout.addWidget(self.take_label)
        self.parameters_group = shape; self.content_stack.addWidget(shape)
        self.content_stack.setCurrentWidget(shape)
        self.arrangement_button.toggled.connect(self.show_arrangement)
        self.details_button = details = QPushButton("Open detailed copy…"); details.clicked.connect(self.detailsRequested.emit); layout.addWidget(details)
        details.setProperty('compact', True); details.setProperty('secondaryAction', True)
        self.refresh()

    def embed_workspace_controls(self, fps_layout, reset_button):
        """Move the actual global FPS control to the document header."""
        fps_layout.addWidget(self.fps_label); fps_layout.addWidget(self.fps)
        self.timeline_controls.hide()
        self.workspace_actions_layout.insertWidget(0, reset_button)
        reset_button.show()

    def show_arrangement(self, expanded):
        self.content_stack.setCurrentWidget(self.arrangement_scroll if expanded else self.parameters_group)
        self.arrangement_button.setText('← Back to editing' if expanded else 'Arrange sections…')
        self.arrangement_button.setToolTip('Return to effects, object and source controls.' if expanded else 'Edit section durations, order and loops.')
        self.emit_reset_context()

    def target(self, document=None):
        document = self.document if document is None else document
        return document if self.scope == 0 else document["sections"][self.index]

    def emit_reset_context(self, *_args):
        self.reset_context_changed.emit(self.reset_label())

    def size_current_tab(self, _index=None):
        # Hidden pages must not leave a tall, empty inspector below a short tab.
        for index in range(self.look_tabs.count()):
            page = self.look_tabs.widget(index)
            page.setSizePolicy(QSizePolicy.Policy.Preferred,
                               QSizePolicy.Policy.Preferred if index == self.look_tabs.currentIndex() else QSizePolicy.Policy.Ignored)
            wrapper = self.look_tabs._scroll_pages.get(page)
            if wrapper: wrapper.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding if index == self.look_tabs.currentIndex() else QSizePolicy.Policy.Ignored)
            page.updateGeometry()
        self.look_tabs.updateGeometry()

    def refresh(self):
        self.updating = True
        try:
            video = self.document.get('footage')
            self.look_tabs.setTabVisible(self.look_tabs.indexOf(self.video_panel), bool(video))
            self.look_tabs.setTabVisible(self.look_tabs.indexOf(self.object_panel), not video)
            self.look_tabs.setTabVisible(2, not video)
            self.details_button.setVisible(not video)
            source_section = self.document['sections'][self.index] if self.scope else None
            self.video_panel.refresh(source_section.get('footage', video) if source_section else video, source_section)
            minimum_frames = sum(int(self.document['sections'][index].get('loops', 1))
                                 for index, _start, _end, _pass in section_placements(self.document))
            self.duration.setMinimum(minimum_frames / self.document["fps"])
            self.duration.setValue(section_ranges(self.document)[-1][1])
            self.fps.setValue(self.document["fps"])
            count = len(self.document["sections"])
            self.timeline_summary.setText(f"{count} {'section' if count == 1 else 'sections'} · {self.duration.value():.2f}s total")
            self.section_combo.clear()
            for index, section in enumerate(self.document["sections"]):
                loops = int(section.get('loops', 1))
                self.section_combo.addItem(f"{index + 1} · {self.document['phrases'][section['phrase']]['name']} · ×{loops}")
            self.section_combo.setCurrentIndex(self.index)
            section = self.document["sections"][self.index]
            self.phrase.setCurrentIndex(self.phrase.findData(section["phrase"]))
            self.section_duration.setMinimum(1 / self.document["fps"])
            self.section_duration.setValue(section["duration"])
            with QSignalBlocker(self.section_loops): self.section_loops.setValue(section.get("loops", 1))
            self.scope_combo.setItemText(0, 'Editing: Whole clip')
            self.scope_combo.setItemText(1, f"Editing: Section {self.index + 1} — {self.document['phrases'][section['phrase']]['name']}")
            self.scope_combo.setCurrentIndex(self.scope)
            self.scope_combo.setToolTip(self.scope_combo.currentText() + ('. Unedited controls follow the whole clip or study.' if self.scope else '. Explicit section overrides take priority.'))
            self.master_panel.set_values(self.document['master'])
            target = self.target()
            needs_base = any('creative' in entry or 'bypassed' in entry
                             for scope in (self.document, *self.document['sections'])
                             for entry in scope['effects'].values())
            base_states = {} if needs_base else None
            compiled = compile_composition(self.document, base_states=base_states)
            self.compiled = compiled
            prefix = section["id"] + ":"
            all_states = list(compiled['states'].values())
            states = [state for name, state in compiled["states"].items() if name.startswith(prefix)] if self.scope else all_states
            label = f"Editing: Section {self.index + 1} — {self.document['phrases'][section['phrase']]['name']}" if self.scope else "Editing: Whole clip"
            context_key = section["id"] if self.scope else None
            authored_states = None
            if base_states is not None:
                authored_states = [state for name, state in base_states.items() if name.startswith(prefix)] if self.scope else list(base_states.values())
            self.effects_panel.set_context(target["effects"], self.document["effects"] if self.scope else {}, states, label, bool(self.scope), (self.scope, context_key), self.document['ink_timing'], all_states, VIDEO_EFFECTS if video else tuple(effect.id for effect in EFFECTS if effect.id != 'subject_cutout'), authored_states=authored_states)
            automation_sections = [section] if self.scope else self.document["sections"]
            counts = {}
            for owner in automation_sections:
                for event in owner.get("automations", ()):
                    counts[event["path"]] = counts.get(event["path"], 0) + 1
            self.effects_panel.set_automation_counts(counts)
            total_events = sum(len(owner.get("automations", ())) for owner in self.document["sections"])
            self.automations_button.setText(f"Automations ({total_events})…" if total_events else "Automations…")
            self.object_panel.refresh(self.effects_panel.summary, target['effects'], self.document['effects'] if self.scope else {}, bool(self.scope), context_key=(self.scope, context_key), scope_label=label.removeprefix('Editing: '))
            for key, control in self.macro_controls.items():
                control.set_value(target["macros"][key], key in target["locks"])
            geometry = target["geometry"]
            self.object_panel.refresh_position(geometry, self.document["geometry"], self.document["canvas"], bool(self.scope))
            self.geometry_shape.clear()
            if self.scope: self.geometry_shape.addItem("From whole clip", "inherit")
            self.geometry_shape.addItem("Original geometry", "original")
            for label in SHAPES: self.geometry_shape.addItem(label, label.lower())
            self.geometry_shape.setCurrentIndex(self.geometry_shape.findData(geometry["shape"]))
            inherited = geometry["shape"] == "inherit"
            resolved = effective_geometry(self.document, section) if self.scope else geometry
            radial = resolved["shape"] in {"circle", "polygon"}
            self.macro_controls["width"].setVisible(not radial)
            for key, control in self.geometry_controls.items():
                value = geometry[key] if key == "height" else resolved[key]
                control.setValue(value * 100 if key == "diameter" else value)
                control.setEnabled(key == "height" or (not inherited and geometry["shape"] != "original"))
                self.geometry_rows[key].setVisible({"height": not radial, "diameter": radial, "sides": resolved["shape"] == "polygon", "rotation": resolved["shape"] not in {"original", "circle"}}[key])
            self.geometry_hint.setText("Diameter is a percentage of image height. The source and ray aperture share the same shape." if radial else "Width and height scale the source and ray aperture. 1× preserves their authored proportions.")
            pristine = not target["effects"] and not target["variation"] and all(value == 1 for value in target["macros"].values()) and geometry == default_geometry(section=bool(self.scope))
            self.take_label.setText("Default controls in this scope" if pristine else (f"Take {target['variation']}" if target["variation"] else "Custom adjustments"))
        finally:
            self.updating = False
        self.emit_reset_context()

    def commit(self, document, action):
        try:
            normalized = normalize_composition(document)
        except ValueError as exc:
            self.index = min(self.index, len(self.document["sections"]) - 1)
            self.refresh(); self.failed.emit(str(exc))
            return
        self.document = normalized
        self.index = min(self.index, len(self.document["sections"]) - 1)
        self.refresh()
        self.changed.emit(self.document, action)

    def select_section(self, index):
        if self.updating or index < 0: return
        self.index = index
        self.scope = 1
        self.refresh()
        self.sectionSelected.emit(index)

    def change_scope(self, index):
        if self.updating: return
        self.scope = index; self.refresh()

    def change_macro(self, key, value):
        if self.updating: return
        document = copy.deepcopy(self.document)
        self.target(document)["macros"][key] = value
        self.commit(document, f"macro:{self.scope}:{self.index}:{key}")

    def change_effect(self, effect_id, entry, action):
        if self.updating: return
        document = copy.deepcopy(self.document)
        effects = self.target(document)["effects"]
        if entry is None:
            effects.pop(effect_id, None)
        else:
            effects[effect_id] = without_timing(entry) if effect_id == 'ink_bloom' else entry
        if action == 'effect-remove':
            from synth_effects import EFFECT_BY_ID
            owners = [document['sections'][self.index]] if self.scope else document['sections']
            for owner in owners:
                events = [event for event in owner.get('automations', ()) if event['path'] not in EFFECT_BY_ID[effect_id].paths]
                if events: owner['automations'] = events
                else: owner.pop('automations', None)
        if action == 'effect-remove' and not self.scope:
            for section in document['sections']:
                section['effects'].pop(effect_id, None)
        self.commit(document, f"{action}:{self.scope}:{self.index}:{effect_id}")

    def add_effect_instance(self, effect_id):
        from synth_instances import base_id, REPEATABLE, document_instance_ids, MAX_INSTANCES
        from synth_effects import effect_preset
        if base_id(effect_id) not in REPEATABLE: return
        numbers = [int(key.split('@')[1]) for key in document_instance_ids(self.document)]
        number = max([1, *numbers]) + 1
        if number > MAX_INSTANCES:
            QMessageBox.information(self, 'Effect instances', 'This composition already uses the maximum number of Tape damage passes.'); return
        identifier = f'{base_id(effect_id)}@{number}'
        # A clean pass contributes nothing until the artist edits or animates it.
        self.change_effect(identifier, effect_preset(identifier, 3), 'effect-instance-add')
        self.effects_panel.inspect_effect(identifier)

    def automation_section_id(self):
        if self.scope: return self.document['sections'][self.index]['id']
        time = self.playhead_seconds()
        for index, start, end, repetition in section_placements(self.document):
            if start <= time < end: return self.document['sections'][index]['id']
        return self.document['sections'][-1]['id']

    def _show_automation_dialog(self, dialog):
        self.automation_dialogs.append(dialog)
        def finished():
            if dialog in self.automation_dialogs: self.automation_dialogs.remove(dialog)
            dialog.deleteLater()
        dialog.finished.connect(finished); dialog.setModal(True); dialog.show()
        return dialog

    def open_automation(self, path=None, section_id=None, event_id=None):
        from synth_automation_ui import AutomationEditor
        return self._show_automation_dialog(AutomationEditor(self, path, section_id, event_id))

    def open_automation_list(self, path=None):
        from synth_automation_ui import AutomationList
        return self._show_automation_dialog(AutomationList(self, path))

    def parameter_automation(self, path):
        if self.effects_panel.automation_counts.get(path, 0): return self.open_automation_list(path)
        return self.open_automation(path)

    def save_automation(self, section_id, event, old_section=None, old_id=None):
        document = copy.deepcopy(self.document)
        if old_id:
            previous = next(s for s in document['sections'] if s['id'] == old_section)
            previous['automations'] = [e for e in previous.get('automations', ()) if e['id'] != old_id]
        owner = next(s for s in document['sections'] if s['id'] == section_id)
        owner.setdefault('automations', []).append(event)
        normalized = normalize_composition(document)  # Draft errors remain inside the editor.
        if normalized != self.document: self.commit(normalized, 'automation-apply')

    def change_automation(self, section_id, event_id, operation, start_fraction=None):
        if operation == 'edit': return self.open_automation(section_id=section_id, event_id=event_id)
        document = copy.deepcopy(self.document)
        owner = next(s for s in document['sections'] if s['id'] == section_id)
        event = next(e for e in owner.get('automations', ()) if e['id'] == event_id)
        duplicate_id = None
        if operation == 'duplicate':
            from synth_automation import duplicate_automation
            duplicate = duplicate_automation(owner['automations'], event_id)
            owner['automations'].append(duplicate); duplicate_id = duplicate['id']
        elif operation == 'remove': owner['automations'].remove(event)
        elif operation == 'toggle': event['enabled'] = not event['enabled']
        elif operation == 'move': event['start_fraction'] = start_fraction
        else: raise ValueError('Unknown automation operation')
        normalized = normalize_composition(document)
        if duplicate_id: compile_composition(normalized)
        if normalized != self.document: self.commit(normalized, 'automation-' + operation)
        return duplicate_id

    def timeline_automation(self, section_id, event_id, operation, start_fraction=None):
        try: return self.change_automation(section_id, event_id, operation, start_fraction)
        except ValueError as exc: self.failed.emit(str(exc))

    def show_timing_scope(self, timing):
        timing = timing and self.effects_panel.focused and self.look_tabs.currentIndex() == 0
        master = self.look_tabs.currentWidget() is self.master_panel
        self.scope_combo.setVisible(not (timing or master))
        self.timing_scope_label.setVisible(timing)
        self.master_scope_label.setVisible(master)
        self.source_scope_label.setVisible(False)
        self.take_label.setVisible(not master)

    def change_video(self, key, value):
        if self.updating: return
        document = copy.deepcopy(self.document)
        target = self.target(document)
        if self.scope: target.setdefault('footage', copy.deepcopy(document['footage']))
        target['footage'][key] = value
        self.commit(document, f'video:{self.scope}:{self.index}:{key}')

    def change_video_source_mode(self, independent):
        if self.updating or not self.scope: return
        document = copy.deepcopy(self.document); section = self.target(document)
        if independent: section.setdefault('footage', copy.deepcopy(document['footage']))
        else: section.pop('footage', None)
        self.commit(document, 'video-source-mode')

    def change_video_speed(self, rate, match_duration):
        if self.updating or not self.scope: return
        from synth_composition import stretch_section
        section = self.document['sections'][self.index]
        if match_duration:
            duration = section['duration'] * section.get('video_rate', 1.) / rate
            document = stretch_section(self.document, section['id'], duration, 'video')
        else:
            document = copy.deepcopy(self.document)
            document['sections'][self.index]['video_rate'] = rate
        self.commit(document, 'video-speed')

    def resize_video_duration(self, duration):
        if self.scope:
            from synth_composition import stretch_section
            section = self.document['sections'][self.index]
            document = stretch_section(self.document, section['id'], duration, 'effects')
            self.commit(document, 'video-trim-duration')
        else: self.resize_clip(duration)

    def apply_video_treatment(self, index):
        self.commit(apply_treatment(self.document, index), 'video-treatment')
        self.look_tabs.setCurrentWidget(self.effects_panel)

    def change_object(self, kind):
        if self.updating: return
        document = select_subject(self.document, kind, self.index if self.scope else None)
        self.commit(document, f'object:{self.scope}:{self.index}')

    def reset_object_position(self):
        if self.updating: return
        document = copy.deepcopy(self.document)
        self.target(document)['geometry'].update(position_x=0., position_y=0.)
        self.commit(document, 'object-position-reset')

    def restore_object(self):
        if self.updating: return
        self.commit(restore_subject(self.document, self.index if self.scope else None), 'object-restore')

    def change_object_parameter(self, effect, path, value):
        if self.updating: return
        entry = copy.deepcopy(self.target()['effects'].get(effect, {'mode': 'recipe', 'params': {}}))
        entry['params'][path] = value
        if path == 'ink_bloom.artwork' and value:
            entry['params']['ink_bloom.shape'] = 5
        self.change_effect(effect, entry, f'effect-param:{path}')

    def reset_object_parameter(self, effect, path):
        if self.updating: return
        entry = copy.deepcopy(self.target()['effects'][effect]); entry['params'].pop(path, None)
        self.change_effect(effect, entry, 'effect-reset-param')

    def open_object_details(self, effect, timing):
        from synth_creative import CREATIVE_CONTROLS
        self.effects_panel.inspect_effect(effect)
        self.effects_panel.parameter_tabs.setCurrentIndex((0 if timing else 1) if effect in CREATIVE_CONTROLS else (1 if timing else 0))
        self.look_tabs.setCurrentWidget(self.effects_panel)

    def change_master(self, key, value):
        if self.updating: return
        document = copy.deepcopy(self.document)
        document['master'][key] = value
        self.commit(document, 'master-toggle' if key == 'enabled' else f'master:{key}')

    def reset_master(self):
        if self.updating: return
        document = copy.deepcopy(self.document); document['master'] = normalize_master()
        self.commit(document, 'master-reset')

    def change_ink_timing(self, path, value):
        if self.updating: return
        document = copy.deepcopy(self.document)
        edit_shared_timing(document, path, value)
        self.commit(document, f'ink-timing:{path}')

    def reset_ink_timing(self):
        if self.updating: return
        document = copy.deepcopy(self.document); restore_shared_timing(document)
        self.commit(document, 'ink-timing-reset')

    def change_shape(self, index):
        if self.updating or index < 0: return
        document = copy.deepcopy(self.document)
        geometry = self.target(document)["geometry"]
        if geometry["shape"] == "inherit":
            for key in ("diameter", "sides", "rotation"):
                geometry[key] = document["geometry"][key]
        geometry["shape"] = self.geometry_shape.itemData(index)
        self.commit(document, "shape")

    def change_geometry(self, key, value):
        if self.updating: return
        document = copy.deepcopy(self.document)
        self.target(document)["geometry"][key] = value
        self.commit(document, f"geometry:{self.scope}:{self.index}:{key}")

    def lock_macro(self, key, locked):
        if self.updating: return
        document = copy.deepcopy(self.document)
        target = self.target(document)
        target["locks"] = [item for item in target["locks"] if item != key] + ([key] if locked else [])
        self.commit(document, "lock")

    def resize_clip(self, duration):
        if self.updating: return
        document = copy.deepcopy(self.document); fps = document["fps"]
        if document.get('timeline_loops'):
            placements = section_placements(document)
            factor = duration / placements[-1][2]
            for section in document['sections']:
                section['duration'] = max(1, round(section['duration'] * fps * factor)) / fps
            self.commit(document, 'duration'); return
        loops = [int(section.get("loops", 1)) for section in document["sections"]]
        frames = max(sum(loops), round(duration * fps))
        # Proportional boundaries retain an exact total on the output frame grid.
        original = section_ranges(document); total = original[-1][1]; cursor = 0
        for index, section in enumerate(document["sections"]):
            remaining = sum(loops[index + 1:])
            boundary = min(frames - remaining, max(cursor + loops[index], round(original[index][1] / total * frames)))
            section["duration"] = max(1, round((boundary - cursor) / loops[index])) / fps; cursor += round(section["duration"] * fps) * loops[index]
        self.commit(document, "duration")

    def change_fps(self, fps):
        if self.updating: return
        document = copy.deepcopy(self.document); document["fps"] = fps
        for section in document["sections"]:
            section["duration"] = max(1, round(section["duration"] * fps)) / fps
        self.commit(document, "fps")

    def resize_section(self, duration):
        self.stretch_section(self.document['sections'][self.index]['id'], duration)

    def stretch_section(self, identifier, duration):
        if self.updating: return
        from synth_composition import stretch_section
        try:
            document = stretch_section(self.document, identifier, duration, self.resize_mode)
        except ValueError as exc:
            self.refresh(); self.failed.emit(str(exc)); return
        if document != self.document:
            self.commit(document, 'section-stretch')

    def stretch_sections(self, identifiers, factor):
        if self.updating: return
        from synth_composition import stretch_sections
        try:
            document = stretch_sections(self.document, identifiers, factor, self.resize_mode)
        except ValueError as exc:
            self.refresh(); self.failed.emit(str(exc)); return
        if document != self.document:
            self.commit(document, 'sections-stretch')

    def resize_section_loops(self, loops):
        if self.updating: return
        document = copy.deepcopy(self.document); document["sections"][self.index]["loops"] = int(loops)
        self.commit(document, "section-loops")

    def loop_sections(self, identifiers, count):
        """One undoable operation; multi-selection repeats a shared sequence."""
        document = copy.deepcopy(self.document)
        selected = set(identifiers)
        members = [section['id'] for section in document['sections'] if section['id'] in selected]
        if not members or len(members) != len(selected): return
        groups = document.get('timeline_loops', [])
        existing = next((group for group in groups if set(group['sections']) == selected), None)
        if len(members) == 1 and existing is None:
            section = next(section for section in document['sections'] if section['id'] == members[0])
            section['loops'] = min(32, int(section.get('loops', 1)) + 1) if count == 0 else count
        else:
            loops = min(32, existing['loops'] + 1) if count == 0 and existing else (2 if count == 0 else count)
            groups = [group for group in groups if not selected.intersection(group['sections'])]
            if loops > 1: groups.append({'sections': members, 'loops': loops})
            elif count == 1:
                for section in document['sections']:
                    if section['id'] in selected: section['loops'] = 1
            if groups: document['timeline_loops'] = groups
            else: document.pop('timeline_loops', None)
        if document != self.document: self.commit(document, 'timeline-loop')

    def change_phrase(self, index):
        if self.updating or index < 0: return
        document = copy.deepcopy(self.document); document["sections"][self.index]["phrase"] = self.phrase.itemData(index)
        self.commit(document, "phrase")

    def _new_id(self, document):
        ids = {section["id"] for section in document["sections"]}
        index = 1
        while f"section-{index}" in ids: index += 1
        return f"section-{index}"

    def duplicate_section(self):
        return self.duplicate_sections((self.document['sections'][self.index]['id'],))

    def duplicate_sections(self, identifiers):
        """Copy a selection as one block, keeping complete sequence loops independent."""
        if self.updating or isinstance(identifiers, (str, bytes)): return
        try: selected = set(identifiers)
        except TypeError: return
        sections = self.document['sections']
        positions = [i for i, section in enumerate(sections) if section['id'] in selected]
        if not positions or len(positions) != len(selected): return
        if len(sections) + len(positions) > 64:
            self.failed.emit('Use at most 64 sections. Remove sections before duplicating this selection.'); return
        document = copy.deepcopy(self.document)
        copies = []; mapping = {}
        insertion = positions[-1] + 1
        for offset, index in enumerate(positions):
            section = copy.deepcopy(sections[index]); old_id = section['id']
            section['id'] = self._new_id(document); mapping[old_id] = section['id']
            document['sections'].insert(insertion + offset, section); copies.append(section['id'])
        for group in self.document.get('timeline_loops', ()):
            if set(group['sections']).issubset(selected):
                document.setdefault('timeline_loops', []).append({
                    'sections': [mapping[key] for key in group['sections']], 'loops': group['loops']})
        try:
            normalized = normalize_composition(document)
            compile_composition(normalized)
        except ValueError as exc:
            self.failed.emit(str(exc)); return
        self.index = insertion
        self.commit(normalized, 'sections-duplicate'); self.sectionSelected.emit(self.index)
        return tuple(copies)

    def add_section(self):
        if len(self.document["sections"]) >= 64: return
        document = copy.deepcopy(self.document)
        phrase_key = self.phrase.currentData(); phrase = document["phrases"][phrase_key]
        section = {"id": self._new_id(document), "phrase": phrase_key, "duration": phrase["end"] - phrase["start"], "loops": 1, "macros": neutral_macros(), "variation": 0, "locks": []}
        document["sections"].insert(self.index + 1, section); self.index += 1
        self.commit(document, "add"); self.sectionSelected.emit(self.index)

    def remove_section(self):
        if len(self.document["sections"]) <= 1: return
        document = copy.deepcopy(self.document)
        removed = document['sections'][self.index]['id']
        del document["sections"][self.index]
        for group in document.get('timeline_loops', []):
            group['sections'] = [key for key in group['sections'] if key != removed]
        if 'timeline_loops' in document:
            document['timeline_loops'] = [group for group in document['timeline_loops'] if group['sections']]
        self.commit(document, "remove"); self.sectionSelected.emit(self.index)

    def reorder_sections(self, identifiers, before_id):
        """Move a stable-ID selection as one block, retaining document order."""
        if self.updating or isinstance(identifiers, (str, bytes)): return
        try:
            selected = set(identifiers)
        except TypeError:
            return
        sections = self.document['sections']
        known = {section['id'] for section in sections}
        if not selected or not selected.issubset(known): return
        if before_id is not None and (not isinstance(before_id, str) or
                before_id not in known or before_id in selected): return
        moved = [section for section in sections if section['id'] in selected]
        remaining = [section for section in sections if section['id'] not in selected]
        position = len(remaining) if before_id is None else next(
            index for index, section in enumerate(remaining) if section['id'] == before_id)
        reordered = remaining[:position]+moved+remaining[position:]
        if [section['id'] for section in reordered] == [section['id'] for section in sections]: return
        current = sections[self.index]['id']
        document = copy.deepcopy(self.document)
        document['sections'] = copy.deepcopy(reordered)
        self.index = next(index for index, section in enumerate(reordered) if section['id'] == current)
        self.commit(document, 'section-reorder')
        self.sectionSelected.emit(self.index)

    def move_section(self, delta):
        target = self.index + delta
        if not 0 <= target < len(self.document["sections"]): return
        document = copy.deepcopy(self.document)
        document["sections"][self.index], document["sections"][target] = document["sections"][target], document["sections"][self.index]
        self.index = target; self.commit(document, "move"); self.sectionSelected.emit(self.index)

    def new_take(self):
        self.commit(vary_composition(self.document, None if self.scope == 0 else self.index), "take")

    def _pending_text_records(self):
        controls = list(self.object_panel.control_cache.values())
        controls += [control for members in self.effects_panel.control_cache.values() for control in members.values()]
        section_ids = {section['id'] for section in self.document['sections']}
        return [(control, context, draft) for control in controls
                for context, draft in control.pending_text_drafts()
                if not (isinstance(context, tuple) and len(context) == 2 and
                        context[0] == 1 and context[1] not in section_ids)]

    def pending_text_edits(self):
        """Visible and hidden unapplied wording, across retained editing scopes."""
        return [(control.input, draft['text']) for control, _context, draft in self._pending_text_records()]

    def prepare_text_save(self):
        """Validate all drafts, then author them together in their original scopes."""
        from synth_text import validate_text
        from synth_effects import state_values
        records = self._pending_text_records()
        if not records: return True
        grouped = {}
        for control, context, draft in records:
            value = validate_text(draft['text'])
            if not isinstance(context, tuple) or len(context) != 2 or context[0] not in (0, 1):
                raise ValueError('The wording draft no longer has an editing scope. Apply it before saving.')
            previous = grouped.get(context)
            if previous is not None and previous != value:
                raise ValueError('The text editors contain different unapplied wording in the same scope. Apply the text you want before saving.')
            grouped[context] = value
        compiled = compile_composition(self.document)
        for _control, context, draft in records:
            scope, identifier = context
            if scope and not any(section['id'] == identifier for section in self.document['sections']):
                raise ValueError('A wording draft belongs to a removed section. Apply or discard it before saving.')
            states = [state for name, state in compiled['states'].items() if not scope or name.startswith(identifier + ':')]
            original_target = next(section for section in self.document['sections'] if section['id'] == identifier) if scope else self.document
            baseline = original_target['effects'].get('text', {}).get('params', {}).get('text.content')
            if baseline is None and scope: baseline = self.document['effects'].get('text', {}).get('params', {}).get('text.content')
            if baseline is None:
                values = [state_values(state)[0]['text.content'] for state in states]
                baseline = draft['value'] if draft['value'] in values else values[0]
            if baseline != draft['value']:
                raise ValueError('The authored wording changed while a draft was pending. Apply the wording you want before saving.')
        document = copy.deepcopy(self.document)
        for (scope, identifier), value in grouped.items():
            target = next(section for section in document['sections'] if section['id'] == identifier) if scope else document
            entry = target['effects'].setdefault('text', {'mode': 'recipe', 'params': {}})
            entry['params']['text.content'] = value
        self.commit(document, 'text-save')
        for control, context, draft in records: control.acknowledge_text_draft(context, draft['text'])
        return True

    def reset_label(self):
        if self.arrangement_button.isChecked(): return ''
        page = self.look_tabs.currentWidget()
        if page is self.master_panel: return 'Reset master'
        if page is self.object_panel: return 'Restore object controls'
        if page is self.video_panel: return 'Reset source controls'
        if page is self.effects_panel:
            if self.effects_panel.focused:
                if self.effects_panel.effect_id == 'ink_bloom' and self.effects_panel.parameter_tabs.currentIndex() == 1:
                    return 'Restore shared timing'
                return 'Restore this effect'
            return ''
        return 'Reset finishing'

    def reset_controls(self):
        if self.arrangement_button.isChecked(): return
        page = self.look_tabs.currentWidget()
        if page is self.master_panel:
            self.reset_master(); return
        if page is self.effects_panel and self.effects_panel.focused:
            if self.effects_panel.effect_id == 'ink_bloom' and self.effects_panel.parameter_tabs.currentIndex() == 1:
                self.reset_ink_timing()
            else: self.effects_panel.restore_effect()
            return
        if page is self.effects_panel: return
        document = copy.deepcopy(self.document); target = self.target(document)
        if page is self.object_panel:
            from synth_subject import SOURCE_EFFECTS
            for key in SOURCE_EFFECTS: target['effects'].pop(key, None)
            target['geometry'] = default_geometry(section=bool(self.scope))
            target['macros']['width'] = 1.
            action = 'object-reset'
        elif page is self.video_panel:
            from synth_video import normalize_footage
            raw = copy.deepcopy(target.get('footage', document['footage']))
            for key in self.video_panel.controls:
                if key not in ('in', 'out'): raw.pop(key, None)
            for key in ('fit', 'end_mode', 'audio'): raw.pop(key, None)
            target['footage'] = normalize_footage(raw)
            action = 'video-reset'
        else:
            for key in MACROS:
                if key != 'width': target['macros'][key] = 1.
            action = 'finishing-reset'
        self.commit(document, action)


class CachedRangeStrip(QWidget):
    """Cached absolute frame ranges aligned with the transport slider."""
    rangesChanged = Signal()
    def __init__(self, slider):
        super().__init__()
        self.slider = slider
        self.ranges = []
        self.setFixedHeight(3)
        self.setAccessibleName('Cached preview ranges')
        self.setToolTip('Highlighted ranges are cached at the current preview quality.')

    def set_ranges(self, ranges):
        self.ranges = list(ranges)
        self.setAccessibleDescription(f'{sum(b-a for a,b in self.ranges)} frames cached')
        self.update()
        self.rangesChanged.emit()

    def paintEvent(self, event):
        painter = QPainter(self)
        origin = self.mapFromGlobal(self.slider.mapToGlobal(QPoint(0, 0))).x()
        width = self.slider.width()
        count = max(1, self.slider.maximum() + 1)
        painter.fillRect(QRectF(origin, 0, width, 2), QColor(COLORS['border']))
        for start, end in self.ranges:
            painter.fillRect(QRectF(origin + width*start/count, 0, max(1, width*(end-start)/count), 2), QColor(COLORS['muted']))
