"""D01 identifies the real owner without changing selection, timing or recipes."""
import copy
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import QEvent, QThreadPool
from PySide6.QtWidgets import QApplication, QMessageBox

from synth_composition import compile_composition
from synth_montage import add_asset, insert_clip, load_montage, new_montage
from synth_montage_ui import MontageWindow
from synth_studio import SynthStudio
from synth_starting_points import new_piece


@pytest.fixture
def workspace(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(SynthStudio, 'request_frame', lambda *_: None)
    monkeypatch.setattr(SynthStudio, 'schedule_auto_preparation', lambda *_: None)
    monkeypatch.setattr(MontageWindow, 'request_frame', lambda *_: None)
    monkeypatch.setattr(MontageWindow, 'initialize_media', lambda *_: None)
    monkeypatch.setattr(QMessageBox, 'question', lambda *_: QMessageBox.StandardButton.Discard)
    monkeypatch.setattr(QMessageBox, 'warning', lambda *_: QMessageBox.StandardButton.Discard)
    doc = new_piece('shape'); doc['name'] = 'A <B> & C'
    second = copy.deepcopy(doc['sections'][0]); second['id'] = 'second'
    doc['sections'].append(second)
    window = SynthStudio(composition=doc); window.show(); app.processEvents()
    yield window
    window.close(); QThreadPool.globalInstance().waitForDone(5000)
    window.deleteLater(); app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_context_separates_selection_editing_and_playback_without_editing(workspace):
    window = workspace; panel = window.composer
    original = copy.deepcopy(window.composition); compiled = copy.deepcopy(window.sequence)
    window.section_timeline.select_at(1)
    assert panel.scope == 0
    assert window.context_header.location.text() == 'Composition · A <B> & C'
    assert 'Selected: Clip 2' in window.timeline_context.text()
    assert 'Editing: Composition' in window.timeline_context.text()
    panel.change_scope(1)
    assert 'Editing: Clip 2' in window.timeline_context.text()
    window.preview_scope.setCurrentIndex(1)
    assert 'Playback: Selected clips' in window.timeline_context.text()
    selection = set(window.section_timeline.selected_ids)
    window.timeline.setValue(window.timeline.maximum())
    assert window.section_timeline.selected_ids == selection and panel.scope == 1
    panel.arrangement_button.click()
    assert 'Editing: Clip timing / composition duration' in window.timeline_context.text()
    panel.arrangement_done.click()
    assert 'Editing: Clip 2' in window.timeline_context.text()
    assert window.composition == original and window.sequence == compiled
    assert window.undo_compositions == [] and not window.has_unsaved_changes()


def test_global_pages_show_true_scope_and_restore_local_target(workspace):
    window = workspace; panel = window.composer
    panel.select_section(1); original = copy.deepcopy(window.composition)
    for page, reason in ((panel.master_panel, 'Master'), (window.performance_panel, 'Perform')):
        panel.look_tabs.setCurrentWidget(page)
        assert panel.scope_combo.isVisible() and not panel.scope_combo.isEnabled()
        assert panel.scope == 1 and panel.scope_combo.currentIndex() == 1
        assert panel.scope_combo.currentText().startswith('Return scope: Clip 2')
        assert reason in panel.master_scope_label.text()
        assert 'all clips in this composition' in panel.master_scope_label.text()
        assert 'Editing: All clips' in window.timeline_context.text()
        assert window.section_timeline.editing_section_id is None
        panel.look_tabs.setCurrentWidget(panel.object_panel)
        assert panel.scope_combo.isEnabled()
        assert panel.scope_combo.currentText().startswith('Editing: Clip 2')
        assert window.section_timeline.editing_section_id == 'second'
    assert window.composition == original and not window.undo_compositions


def open_montage(window, tmp_path):
    doc, key = add_asset(new_montage(window.composition['canvas'], 30), 'Shared material', study=window.composition)
    doc, _ = insert_clip(doc, key, frames=30)
    doc, _ = insert_clip(doc, key, frames=30)
    return window.open_montage(document=doc, path=tmp_path / 'montage.json')


def test_nested_context_saves_only_edited_use_and_names_the_file_owner(workspace, tmp_path):
    window = workspace; montage = open_montage(window, tmp_path)
    original = copy.deepcopy(montage.document); key = montage.document['clips'][1]['id']
    montage.seek(12); montage.zoom(150)
    editor = montage.edit_clip(key); panel = editor.composer
    assert 'Block 02' in editor.context_header.location.text()
    assert editor.save_button.text() == 'Save montage'
    assert 'complete montage' in editor.save_button.toolTip()
    panel.change_scope(0)
    assert panel.scope_combo.currentText() == 'Editing: Block composition'
    panel.look_tabs.setCurrentWidget(panel.master_panel)
    assert 'all internal clips in this block' in panel.master_scope_label.text()
    panel.master_panel.controls['contrast'].setValue(140)
    assert editor.context_header.state.text() == 'Unsaved changes'
    assert window.workspace_navigation.save()
    saved = load_montage(montage.path)
    assert saved['clips'][1]['document']['master']['contrast'] == 1.4
    assert saved['assets'] == original['assets'] and saved['clips'][0] == original['clips'][0]
    assert editor.context_header.state.text() == 'Saved'
    assert window.workspace_navigation.return_to_montage()
    assert montage.frame == 12 and montage.selected == {key} and montage.timeline.scale == 150
    assert 'Block 02' in montage.status.text() and 'Montage saved' in montage.status.text()
    assert montage.context_header.state.text() == 'Saved'
    assert 'Playback: Entire montage' in montage.timeline_context.text()
    editor = montage.edit_clip(key)
    assert editor.composition['master']['contrast'] == 1.4
    assert window.workspace_navigation.return_to_montage()
    assert montage.status.text() == 'No block changes · Montage saved'
    assert montage.document == saved


def test_material_playhead_and_empty_selection_do_not_claim_an_edit_target(workspace, tmp_path):
    montage = open_montage(workspace, tmp_path)
    montage.select_blocks(set()); before = copy.deepcopy(montage.document)
    montage.library.setCurrentRow(0); montage.seek(15)
    assert 'Selected: None' in montage.timeline_context.text()
    assert 'Editing: No target' in montage.timeline_context.text()
    montage.select_all()
    assert 'Selected: 2 blocks' in montage.timeline_context.text()
    assert montage.document == before


def test_sound_and_visuals_use_the_same_nested_owner(workspace, tmp_path, monkeypatch):
    from synth_visual_sound import instrument_sound
    montage = open_montage(workspace, tmp_path)
    editor = montage.edit_clip(montage.document['clips'][0]['id'])
    monkeypatch.setattr(editor, 'audition_visual_sound', lambda *_: None)
    monkeypatch.setattr(editor, 'prepare_visual_sound', lambda *_: None)
    editor.apply_visual_sound(instrument_sound()); editor.visual_sound_debounce.stop()
    editor.open_visual_sound(); dialog = editor.visual_sound_dialog
    assert dialog.context_title.text() == editor.context_header.location.text()
    assert 'All internal clips in this block' in dialog.workspace_hint.text()
    assert dialog.save_project_button.text() == 'Save montage'
    dialog.tabs.setCurrentIndex(dialog.performance_tab)
    assert dialog.workspace_hint.text().startswith('Visuals · All internal clips in this block')
    assert 'All internal clips in this block' in dialog.performance_panel.scope_hint.text()


def test_detailed_copy_remains_an_independent_document(workspace):
    before = copy.deepcopy(workspace.composition)
    workspace.open_detailed_copy(); child = workspace.detail_windows[-1]
    assert child.context_header.location.text().startswith('Detailed sequence copy')
    assert 'Independent document' in child.legacy_scope.text()
    assert child.save_button.accessibleName() == 'Save sequence'
    assert workspace.composition == before and workspace.sequence == compile_composition(before)


def test_auxiliary_editors_retain_nested_document_identity(workspace, tmp_path):
    from synth_automation_ui import AutomationList
    from synth_exploration_ui import SnapshotsDialog
    from synth_soundtrack_ui import SoundtrackDialog
    from synth_color_ui import ColorPicker, COLORS
    montage = open_montage(workspace, tmp_path)
    editor = montage.edit_clip(montage.document['clips'][1]['id'])
    original = copy.deepcopy(editor.composition)
    color = dict(hsv=(.2, .8, .7), shot_label='Clip 1', section_id='section-1', palette=[])
    dialogs = [AutomationList(editor.composer), SnapshotsDialog(editor),
               SoundtrackDialog(editor), ColorPicker(COLORS[0], color, editor.composer)]
    for dialog in dialogs:
        assert dialog.document_context.text() == editor.context_header.location.text()
        assert 'Block 02' in dialog.document_context.text()
        assert 'complete montage' in dialog.document_context.toolTip()
        dialog.reject()
    assert editor.composition == original and not editor.has_unsaved_changes()
    assert not editor.undo_compositions
