"""Material/target identity, reversible timing drafts and explicit source ranges."""
import copy
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog

from synth_montage import add_asset, insert_clip, load_montage, normalize_montage, replace_clip
from synth_montage_ui import MontageWindow, SourceRangeDialog
from test_synth_montage import project, montage


@pytest.fixture
def window(montage, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(MontageWindow, 'request_frame', lambda *_: None)
    monkeypatch.setattr(MontageWindow, 'initialize_media', lambda *_: None)
    monkeypatch.setattr(SourceRangeDialog, 'preview', lambda *_: None)
    window = MontageWindow(montage); window.show(); app.processEvents()
    yield window
    window.revert_timing(); window.clean = copy.deepcopy(window.document)
    window.close(); app.processEvents()


def choose_range(monkeypatch, start, end=None, *, cancel=False, inspect=None):
    original = QDialog.exec
    def exec(dialog):
        def interact():
            dialog.start.setValue(start)
            if end is not None: dialog.end.setValue(end)
            if inspect: inspect(dialog)
            if cancel: dialog.reject()
            else: QTest.mouseClick(dialog.confirm, Qt.MouseButton.LeftButton)
        QTimer.singleShot(0, interact)
        return original(dialog)
    monkeypatch.setattr(SourceRangeDialog, 'exec', exec)


def test_insert_16_frames_undo_clears_target_and_redo_restores_it(window, monkeypatch):
    # The report's 28-second montage grows by exactly 16/30 seconds.
    doc = copy.deepcopy(window.document)
    next(iter(doc['assets'].values()))['document']['sections'][0]['duration'] = 30
    doc['clips'] = [dict(doc['clips'][0], in_frame=0, frames=840)]
    window.document = normalize_montage(doc); window.clean = copy.deepcopy(window.document); window.refresh()
    original = copy.deepcopy(window.document)
    window.library.setCurrentRow(0); asset = window.library_key()
    choose_range(monkeypatch, 2, 18)
    window.choose_range()
    key = window.active_clip()['id']
    assert sum(c['frames'] for c in window.document['clips']) == 856
    assert (window.source_in.value(), window.length.value()) == (2, 16)
    window.undo()
    assert window.document == original and not window.selected
    assert window.library_key() == asset and 'None' in window.clip_name.text()
    assert window.timing_empty.isVisible() and '—' in window.timing_empty.text()
    assert not window.timing_fields.isVisible() and not window.timing_fields.isEnabled()
    assert not window.apply_timing_button.isEnabled() and not window.edit_button.isEnabled()
    assert not window.replace_button.isEnabled() and window.insert_button.isEnabled()
    window.redo()
    assert window.selected == {key} and window.timing_fields.isVisible()
    assert (window.source_in.value(), window.length.value()) == (2, 16)


def test_material_target_and_playhead_are_independent_and_multiselect_is_explicit(window):
    original = copy.deepcopy(window.document); key = original['clips'][0]['id']
    window.select_clip(key); window.library.setCurrentRow(0); window.seek(19)
    assert window.selected == {key} and window.active_clip()['id'] == key
    assert 'Material source: Study' in window.material_context.text()
    assert 'Block 01' in window.clip_name.text() and window.replace_button.isEnabled()
    window.select_all()
    assert window.active_clip() is None and '2 blocks' in window.clip_name.text()
    assert not window.replace_button.isEnabled() and not window.edit_button.isEnabled()
    assert not window.copy_button.isEnabled() and not window.timing_fields.isEnabled()
    assert window.remove_button.isEnabled() and window.duplicate_button.isEnabled()
    assert window.document == original


def test_timing_draft_stay_discard_apply_and_undo_have_named_destination(window, monkeypatch):
    first, second = [c['id'] for c in window.document['clips']]
    original = copy.deepcopy(window.document); window.select_clip(first)
    window.length.setValue(16)
    assert window.has_timing_draft() and 'Block 01' in window.timing_state.text()
    assert window.document == original and window.apply_timing_button.isEnabled()
    # Library and non-timing document changes retain the draft.
    window.library.setCurrentRow(0); window.refresh()
    assert window.length.value() == 16
    monkeypatch.setattr(window, 'choose_pending_timing', lambda *_: 'stay')
    assert not window.select_clip(second) and window.selected == {first}
    monkeypatch.setattr(window, 'choose_pending_timing', lambda *_: 'discard')
    assert window.select_clip(second) and window.document == original
    window.select_clip(first); window.length.setValue(16)
    monkeypatch.setattr(window, 'choose_pending_timing', lambda *_: 'apply')
    assert window.select_clip(second)
    assert window.document['clips'][0]['frames'] == 16 and window.length.value() == 10
    assert not window.has_timing_draft()
    window.undo(); assert window.document == original and window.selected == {first}


def test_invalid_timing_stays_pending_and_keyboard_selection_does_not_seek(window, monkeypatch):
    first, second = [c['id'] for c in window.document['clips']]
    window.select_clip(first); window.seek(7); original = copy.deepcopy(window.document)
    window.length.setValue(100)
    assert not window.apply_timing()
    assert 'extends beyond' in window.timing_state.text() and window.has_timing_draft()
    monkeypatch.setattr(window, 'choose_pending_timing', lambda *_: 'stay')
    QTest.keyClick(window.timeline, Qt.Key.Key_Right)
    assert window.selected == {first} and window.frame == 7
    window.revert_timing()
    assert window.document == original and not window.has_timing_draft()
    QTest.keyClick(window.timeline, Qt.Key.Key_Right)
    assert window.selected == {second} and window.frame == 12


def test_readonly_timing_precision_survives_editing_only_duration(window):
    doc = copy.deepcopy(window.document)
    doc['clips'][0].update(in_frame=3.123456789123456, speed=.123456789123456)
    window.document = normalize_montage(doc); window.refresh()
    window.select_clip(doc['clips'][0]['id'])
    assert not window.has_timing_draft()
    window.finish_timing_input(); assert not window.has_timing_draft()
    window.length.setValue(13); assert window.apply_timing()
    actual = window.document['clips'][0]
    assert actual['in_frame'] == doc['clips'][0]['in_frame']
    assert actual['speed'] == doc['clips'][0]['speed']
    window.undo(); assert window.document == doc


def test_typing_can_apply_directly_without_tab_and_revert_cancels_input(window):
    window.select_clip(window.document['clips'][0]['id'])
    window.length.setFocus(); window.length.selectAll(); QTest.keyClicks(window.length, '16')
    assert window.apply_timing_button.isEnabled() and window.revert_timing_button.isVisible()
    QTest.mouseClick(window.apply_timing_button, Qt.MouseButton.LeftButton)
    assert window.document['clips'][0]['frames'] == 16 and not window.has_timing_draft()
    window.length.setFocus(); window.length.selectAll(); QTest.keyClicks(window.length, '18')
    QTest.mouseClick(window.revert_timing_button, Qt.MouseButton.LeftButton)
    assert window.length.value() == 16 and not window.has_timing_draft()


def test_save_export_and_close_resolve_pending_timing(window, monkeypatch, tmp_path):
    window.path = tmp_path/'saved.json'; first = window.document['clips'][0]['id']
    window.select_clip(first); window.length.setValue(16)
    monkeypatch.setattr(window, 'choose_pending_timing', lambda *_: 'stay')
    assert not window.save() and not window.path.exists() and not window.may_replace()
    monkeypatch.setattr(window, 'choose_pending_timing', lambda *_: 'apply')
    assert window.save() and load_montage(window.path)['clips'][0]['frames'] == 16
    window.length.setValue(17); captured = []
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *_: (str(tmp_path/'export.mp4'), ''))
    monkeypatch.setattr(window, 'start_export', lambda *_: captured.append(copy.deepcopy(window.document)))
    monkeypatch.setattr(window, 'choose_pending_timing', lambda *_: 'discard')
    window.export_dialog()
    assert captured[0]['clips'][0]['frames'] == 16 and not window.has_timing_draft()


def test_insert_destination_cancel_and_mismatched_rates(window, monkeypatch):
    original = copy.deepcopy(window.document); first = original['clips'][0]['id']
    window.select_clip(first); window.library.setCurrentRow(0)
    def inspect(dialog):
        assert 'After Block 01' in dialog.context.text()
        assert '16 frames at 30 fps' in dialog.note.text()
        assert '0.533s' in dialog.note.text()
        assert 'Source: 25 fps' in dialog.clock.text()
    choose_range(monkeypatch, 2, 18, cancel=True, inspect=inspect)
    window.choose_range(); assert window.document == original and window.selected == {first}
    choose_range(monkeypatch, 2, 18, inspect=inspect)
    window.choose_range()
    assert window.document['clips'][1]['in_frame'] == 2
    assert window.document['clips'][2] == original['clips'][1]
    window.undo(); assert window.document == original and window.selected == {first}


def test_replacement_range_matches_renderer_last_sample_bounds(window):
    key = window.document['clips'][0]['asset']
    target = dict(window.document['clips'][0], speed=1.25)
    dialog = SourceRangeDialog(window.document, key, target=target, destination='Block 01')
    dialog.start.setValue(46)  # Last sample 59.75 / 30 is inside the 2-second source.
    assert dialog.valid and dialog.confirm.isEnabled() and dialog.end.value() == 61
    doc = copy.deepcopy(window.document); doc['clips'][0] = target
    replaced = replace_clip(doc, target['id'], key, 46)
    assert replaced['clips'][0]['speed'] == 1.25 and replaced['clips'][0]['frames'] == 12
    dialog.start.setValue(47)
    assert not dialog.valid and not dialog.confirm.isEnabled()
    with pytest.raises(ValueError, match='beyond'): replace_clip(doc, target['id'], key, 47)
    dialog.reject()


def test_replacement_short_source_is_disabled_and_cancel_preserves_document(window):
    doc = copy.deepcopy(window.document); short = copy.deepcopy(next(iter(doc['assets'].values()))['document'])
    short['sections'][0]['duration'] = .1
    doc, key = add_asset(doc, 'Short source', study=short)
    dialog = SourceRangeDialog(doc, key, target=doc['clips'][0], destination='Block 01')
    assert not dialog.confirm.isEnabled() and 'longer material' in dialog.note.text()
    assert not dialog.end.isEnabled()
    dialog.reject(); assert doc['clips'] == window.document['clips']


def test_replace_keeps_duration_speed_treatment_then_undo_restores(window, monkeypatch):
    original = copy.deepcopy(window.document); target = original['clips'][0]
    window.select_clip(target['id']); window.library.setCurrentRow(0)
    choose_range(monkeypatch, 20, cancel=True)
    window.replace_selected(); assert window.document == original
    choose_range(monkeypatch, 20)
    window.replace_selected()
    result = window.document['clips'][0]
    assert result['frames'] == target['frames'] and result['speed'] == target['speed']
    assert result['in_frame'] == 20 and result['document']['effects']['dye_transfer']['mode'] == 'on'
    assert window.document['clips'][1:] == original['clips'][1:]
    assert window.document['assets'] == original['assets']
    window.undo(); assert window.document == original and window.selected == {target['id']}
    window.redo(); assert window.document['clips'][0] == result
