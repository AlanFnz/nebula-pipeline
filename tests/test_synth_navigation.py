"""One-window document ownership, navigation and save/close routing."""
import copy
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import QThreadPool
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow, QMessageBox

from synth_composition import blank_composition, save_composition
from synth_montage import add_asset, insert_clip, load_montage, new_montage
from synth_montage_ui import MontageWindow
from synth_studio import SynthStudio


@pytest.fixture
def workspace(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(SynthStudio, 'request_frame', lambda *_: None)
    monkeypatch.setattr(SynthStudio, 'schedule_auto_preparation', lambda *_: None)
    monkeypatch.setattr(MontageWindow, 'request_frame', lambda *_: None)
    monkeypatch.setattr(MontageWindow, 'initialize_media', lambda *_: None)
    study = blank_composition(); study['canvas'].update(width=96, height=64)
    study['sections'][0]['duration'] = 2.
    doc, key = add_asset(new_montage(study['canvas'], 30), 'Study', study=study)
    doc, _ = insert_clip(doc, key, frames=30)
    doc, _ = insert_clip(doc, key, frames=30)
    root = SynthStudio(composition=study); root.show()
    montage = root.open_montage(document=doc, path=tmp_path / 'project.json')
    app.processEvents()
    yield root, montage, app
    monkeypatch.setattr(QMessageBox, 'question', lambda *_: QMessageBox.StandardButton.Discard)
    monkeypatch.setattr(QMessageBox, 'warning', lambda *_: QMessageBox.StandardButton.Discard)
    root.close()
    QThreadPool.globalInstance().waitForDone(5000)
    app.processEvents()


def test_enter_return_is_one_window_and_keeps_timing_selection_and_playhead(workspace):
    root, montage, app = workspace
    original = copy.deepcopy(montage.document)
    montage.detail.setCurrentIndex(2)
    montage.seek(12); montage.zoom(150)
    key = montage.document['clips'][0]['id']
    editor = montage.edit_clip(key); app.processEvents()
    assert editor.window() is root and montage.window() is root
    assert editor.quality.currentIndex() == 2
    assert [w for w in app.topLevelWidgets() if isinstance(w, QMainWindow) and w.isVisible()] == [root]
    assert not editor.montage_button.isVisible() and not editor.study_controls.isVisible()
    assert root.preview_suspended and montage.preview_suspended and not editor.preview_suspended
    editor.composer.commit(dict(editor.composition, name='Edited block'), 'name')
    editor.back_to_montage.click(); app.processEvents()
    assert root.workspace_navigation.active is montage and not montage.preview_suspended
    assert montage.frame == 12 and montage.selected == {key}
    assert montage.document['clips'][0]['document']['name'] == 'Edited block'
    assert montage.document['assets'] == original['assets']
    assert montage.document['clips'][1] == original['clips'][1]
    assert [c['frames'] for c in montage.document['clips']] == [30, 30]
    assert montage.editors == []
    assert montage.detail.currentIndex() == 2
    montage.undo(); assert montage.document == original
    montage.redo(); assert montage.document['clips'][0]['document']['name'] == 'Edited block'


def test_unedited_visit_does_not_modify_document(workspace):
    root, montage, _ = workspace
    original = copy.deepcopy(montage.document)
    montage.edit_clip(montage.document['clips'][0]['id'])
    assert root.workspace_navigation.return_to_montage()
    assert montage.document == original and montage.undo_stack == []
    assert montage.document == montage.clean


def test_save_shortcut_inside_block_saves_entire_montage(workspace):
    root, montage, app = workspace
    editor = montage.edit_clip(montage.document['clips'][0]['id'])
    editor.composer.commit(dict(editor.composition, name='Saved from block'), 'name')
    root.activateWindow(); editor.viewer.setFocus(); app.processEvents()
    QTest.keySequence(editor.viewer, QKeySequence(QKeySequence.StandardKey.Save)); app.processEvents()
    assert montage.path.exists()
    saved = load_montage(montage.path)
    assert saved['clips'][0]['document']['name'] == 'Saved from block'
    assert len(saved['clips']) == 2 and saved == montage.clean
    assert root.workspace_navigation.active is editor
    assert not root.windowTitle().endswith('*')


def test_undo_shortcut_only_affects_current_context(workspace):
    root, montage, app = workspace
    original = copy.deepcopy(montage.document)
    editor = montage.edit_clip(montage.document['clips'][0]['id'])
    before = copy.deepcopy(editor.composition)
    editor.composer.commit(dict(editor.composition, name='Undo me'), 'name')
    root.activateWindow(); editor.viewer.setFocus(); app.processEvents()
    QTest.keySequence(editor.viewer, QKeySequence(QKeySequence.StandardKey.Undo)); app.processEvents()
    assert editor.composition == before and montage.document == original
    editor.composer.commit(dict(editor.composition, name='Undo in montage'), 'name')
    root.workspace_navigation.return_to_montage(); montage.monitor.setFocus(); app.processEvents()
    QTest.keySequence(montage.monitor, QKeySequence(QKeySequence.StandardKey.Undo)); app.processEvents()
    assert montage.document == original


def test_cancel_close_keeps_block_and_save_closes_project(workspace, monkeypatch):
    root, montage, app = workspace
    editor = montage.edit_clip(montage.document['clips'][0]['id'])
    editor.composition['name'] = 'Keep this edit'
    monkeypatch.setattr(QMessageBox, 'question', lambda *_: QMessageBox.StandardButton.Cancel)
    assert not root.close()
    assert root.workspace_navigation.active is editor and root.isVisible()
    monkeypatch.setattr(QMessageBox, 'question', lambda *_: QMessageBox.StandardButton.Save)
    path = montage.path
    assert root.close()
    assert load_montage(path)['clips'][0]['document']['name'] == 'Keep this edit'
    app.processEvents()
    assert not any(w.isVisible() for w in app.topLevelWidgets() if isinstance(w, QMainWindow))


def test_invalid_block_duration_stays_in_editor(workspace):
    root, montage, _ = workspace
    original = copy.deepcopy(montage.document)
    editor = montage.edit_clip(montage.document['clips'][0]['id'])
    editor.composition['sections'][0]['duration'] = .1
    assert not root.workspace_navigation.return_to_montage()
    assert root.workspace_navigation.active is editor and montage.document == original
    assert 'Could not update' in editor.status.text()
    editor.composition['sections'][0]['duration'] = 2.


def test_open_composition_from_montage_reuses_window(workspace, monkeypatch, tmp_path):
    root, montage, app = workspace
    path = tmp_path / 'study.json'
    project = blank_composition(); project['name'] = 'Different study'; save_composition(path, project)
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *_: (str(path), ''))
    assert montage.open_dialog()
    assert root.composition['name'] == 'Different study'
    assert root.workspace_navigation.montage is None
    assert root.workspace_navigation.active is root
    assert root.header_host.isVisible() and not root.preview_suspended
    app.processEvents()


def test_export_from_block_commits_and_exports_whole_project(workspace, monkeypatch):
    root, montage, _ = workspace
    editor = montage.edit_clip(montage.document['clips'][0]['id'])
    editor.composition['name'] = 'Export this'
    exports = []
    monkeypatch.setattr(montage, 'export_dialog', lambda: exports.append(copy.deepcopy(montage.document)))
    editor.export_button.click()
    assert exports[0]['clips'][0]['document']['name'] == 'Export this'
    assert len(exports[0]['clips']) == 2
    assert root.workspace_navigation.active is montage
