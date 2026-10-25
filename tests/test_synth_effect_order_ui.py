"""Drag/drop and keyboard reorders participate in normal document history."""
import copy
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import QMimeData, QPoint, QPointF, QThreadPool, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox, QScrollArea

from studio_theme import apply_theme
from synth_composition import blank_composition, compile_composition, save_composition, load_composition
from synth_composer_ui import CompositionPanel
from synth_effect_order_ui import MIME
from synth_effects import effect_preset
from synth_studio import SynthStudio


def document():
    project = blank_composition()
    project['effects'] = {key: effect_preset(key) for key in ('text', 'optical_print', 'broadcast', 'tape@2', 'low_res')}
    return project


@pytest.fixture
def panel():
    app = QApplication.instance() or QApplication([]); apply_theme(app)
    widget = CompositionPanel(document()); widget.resize(440, 700); widget.show()
    widget.effects_panel.show_overview(); app.processEvents()
    yield widget
    widget.close(); widget.deleteLater(); app.processEvents()


class Drop:
    def __init__(self, source, y):
        self._source, self.y, self.accepted = source, y, False
        self.mime = QMimeData(); self.mime.setData(MIME, source.identifier.encode())
    def source(self): return self._source
    def position(self): return QPointF(2, self.y)
    def mimeData(self): return self.mime
    def setDropAction(self, action): self.action = action
    def accept(self): self.accepted = True
    def ignore(self): self.accepted = False


def test_drop_commits_once_preserves_settings_and_reset_restores_recipe(panel):
    effects = panel.effects_panel; rack = effects.applied_host
    before = copy.deepcopy(panel.document)
    original = compile_composition(before)
    changes = []; panel.changed.connect(lambda *args: changes.append(args))
    handle = effects.effect_choices['broadcast'].order_handle
    handle.drag_context = rack.context
    event = Drop(handle, effects.effect_choices['optical_print'].y())
    rack.dragEnterEvent(event); assert event.accepted
    rack.dragMoveEvent(event); assert rack.marker is not None
    rack.dropEvent(event)
    assert event.accepted and len(changes) == 1 and rack.marker is None
    assert effects.project_effect_ids == ('broadcast', 'optical_print', 'tape@2', 'low_res')
    assert panel.document['effects'] == before['effects']
    assert panel.document['sections'] == before['sections']
    # The no-op drop does not create another undo entry.
    handle.drag_context = rack.context
    rack.dropEvent(Drop(handle, effects.effect_choices['optical_print'].y()))
    assert len(changes) == 1
    effects.order_reset.click()
    assert len(changes) == 2 and panel.document == before
    assert compile_composition(panel.document) == original


def test_keyboard_movement_and_scope_guards(panel):
    effects = panel.effects_panel
    handle = effects.effect_choices['optical_print'].order_handle
    assert handle.isVisible()
    assert effects.effect_choices['low_res'].order_handle.isHidden()
    assert effects.effect_choices['low_res'].fixed_order.isVisible()
    QTest.keyClick(handle, Qt.Key.Key_Down, Qt.KeyboardModifier.AltModifier)
    assert effects.project_effect_ids[:2] == ('broadcast', 'optical_print')
    old = copy.deepcopy(panel.document)
    panel.change_scope(1)
    assert effects.order_reset.isHidden() and handle.isHidden()
    effects.move_effect_step('broadcast', 1)
    panel.reorder_effect('broadcast', None)
    assert panel.document == old


def test_cancel_external_and_stale_drag_do_not_edit(panel):
    effects = panel.effects_panel; rack = effects.applied_host
    handle = effects.effect_choices['broadcast'].order_handle
    original = copy.deepcopy(panel.document)
    handle.drag_context = rack.context
    event = Drop(handle, 0)
    rack.dragMoveEvent(event); assert rack.marker is not None
    rack.dragLeaveEvent(event)
    assert rack.marker is None and not rack.scroll_timer.isActive()
    handle.drag_context = 'old document'
    rack.dropEvent(event); assert not event.accepted
    assert panel.document == original


def test_narrow_rack_keeps_actions_visible(panel):
    panel.resize(390, 650); QApplication.processEvents()
    effects = panel.effects_panel
    assert effects.overview.findChild(QScrollArea).horizontalScrollBar().maximum() == 0
    for key in effects.project_effect_ids:
        row = effects.effect_choices[key]
        for action in (row.bypass, row.remove):
            point = action.mapTo(row, QPoint())
            assert 0 <= point.x() and point.x() + action.width() <= row.width()


def test_reorder_undo_redo_and_saved_sequence_match(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([]); apply_theme(app)
    monkeypatch.setattr(SynthStudio, 'request_frame', lambda self: None)
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: QMessageBox.StandardButton.Discard)
    window = SynthStudio(composition=document())
    try:
        panel = window.composer; before = copy.deepcopy(window.composition)
        panel.reorder_effect('broadcast', 'optical_print')
        assert window.has_unsaved_changes()
        reordered = copy.deepcopy(window.composition)
        assert window.sequence['effect_order'] == reordered['effect_order']
        window.undo_composition()
        assert window.composition == before and not window.has_unsaved_changes()
        window.redo_composition()
        assert window.composition == reordered and window.has_unsaved_changes()
        save_composition(tmp_path/'project.json', window.composition)
        assert compile_composition(load_composition(tmp_path/'project.json')) == window.sequence
    finally:
        window.close(); QThreadPool.globalInstance().waitForDone(10000); app.processEvents()
