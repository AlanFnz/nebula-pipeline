"""Starting choices enter the real editor without losing the current document."""
import copy
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import QSettings, QThreadPool, QTimer
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from studio_theme import apply_theme
from synth_composition import load_composition
from synth_new_piece_ui import NewPieceDialog
from synth_starters import starter_composition
from synth_studies import save_study, study_composition
from synth_studio import SynthStudio
from test_synth_video import clip
from test_synth_video_ui import wait_until


@pytest.fixture
def make_window(monkeypatch, tmp_path):
    from pathlib import Path
    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(SynthStudio, 'request_frame', lambda self: None)
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: QMessageBox.StandardButton.Discard)
    windows = []
    def make():
        settings = QSettings(str(tmp_path / 'workspace.ini'), QSettings.Format.IniFormat)
        window = SynthStudio(settings=settings); windows.append(window)
        window.resize(1280, 720); window.show(); app.processEvents()
        return window
    yield make
    for window in windows: window.close()
    QThreadPool.globalInstance().waitForDone(10000)
    app.processEvents()


def choose_material(kind, *, wording=None, model=None, reject=False):
    def choose():
        dialog = QApplication.activeModalWidget()
        assert isinstance(dialog, NewPieceDialog)
        dialog.choices[kind].click()
        if wording is not None: dialog.text.setPlainText(wording)
        if model is not None: dialog.model.setCurrentIndex(dialog.model.findData(model))
        if reject: dialog.reject()
        else: dialog.create.click()
    QTimer.singleShot(0, choose)


@pytest.mark.parametrize('kind,options,subject', [
    ('text', {'wording': 'OUR NEXT PIECE'}, 'text'),
    ('shape', {}, 'signal'),
    ('model', {}, 'silhouette'),
    ('model', {'model': 'particles'}, 'particles'),
])
def test_start_edit_treat_undo_and_save_open_through_workspace(make_window, monkeypatch, tmp_path,
                                                            kind, options, subject):
    window = make_window()
    window.composer.fps.setValue(12)
    window.mark_document_clean()
    choose_material(kind, **options)
    window.new_piece_button.click()
    assert window.composer.object_panel.kind == subject
    assert window.composer.look_tabs.currentWidget() is window.composer.object_panel
    assert window.sequence['duration'] == 6 and window.sequence['fps'] == 12
    assert window.has_unsaved_changes() and window.document_path is None
    window.composer.object_panel.position_controls['x'].setValue(40)
    assert window.composition['geometry']['position_x'] == 40
    if kind == 'text':
        wording = window.composer.object_panel.controls['text.content'].input
        wording.editor.setPlainText('A SECOND IDEA'); wording.apply.click()
        assert window.composition['effects']['text']['params']['text.content'] == 'A SECOND IDEA'
    untreated = copy.deepcopy(window.composition)
    window.composer.look_tabs.setCurrentWidget(window.composer.effects_panel)
    window.composer.effects_panel.add_effect('tape', 0)
    assert 'tape' in window.composer.effects_panel.applied_ids
    treated = copy.deepcopy(window.composition)
    window.undo_composition(); assert window.composition == untreated
    window.redo_composition(); assert window.composition == treated
    path = tmp_path / 'new-work.json'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(path), ''))
    assert window.save_sequence_dialog()
    assert not window.has_unsaved_changes()
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args: (str(path), ''))
    window.load_sequence_dialog()
    assert window.composition == treated == load_composition(path)
    assert not window.has_unsaved_changes()


def test_cancel_starting_dialog_keeps_work_playhead_and_history(make_window):
    window = make_window()
    window.composer.fps.setValue(12)
    window.timeline.setValue(75)
    window.play.setChecked(True)
    before = copy.deepcopy(window.document_state())
    history = copy.deepcopy(window.undo_compositions)
    identity = window.document_identity
    choose_material('model', reject=True)
    window.new_piece_button.click()
    assert window.document_state() == before and window.undo_compositions == history
    assert window.document_identity is identity
    assert window.timeline.value() == 75 and window.play_timer.isActive()


def test_unsaved_cancel_and_invalid_text_leave_document_intact(make_window, monkeypatch):
    window = make_window(); window.composer.fps.setValue(12)
    before = copy.deepcopy(window.document_state())
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: QMessageBox.StandardButton.Cancel)
    choose_material('shape'); window.new_piece_action.trigger()
    assert window.document_state() == before and window.has_unsaved_changes()
    assert not window.create_piece('text', text=' ')
    assert window.document_state() == before


def test_text_validation_and_empty_study_library(make_window):
    window = make_window()
    dialog = NewPieceDialog(window.current_canvas(), 12, [], parent=window)
    assert dialog.create.isEnabled()
    for text in (' ', 'x' * 513, '\n'.join(['line'] * 9)):
        dialog.text.setPlainText(text)
        assert not dialog.create.isEnabled() and dialog.error.text()
    dialog.text.setPlainText('A NEW IDEA'); assert dialog.create.isEnabled()
    dialog.choices['remix'].click(); assert not dialog.create.isEnabled()
    dialog.choices['shape'].click(); assert dialog.create.isEnabled()
    dialog.deleteLater()


def test_remix_uses_saved_canvas_and_never_edits_personal_study(make_window, tmp_path, monkeypatch):
    window = make_window()
    project = starter_composition('text-transmission')
    project['canvas'].update(width=1080, height=1920)
    project['fps'] = 12
    identifier = save_study(project, 'My original')
    original = study_composition(identifier)
    window.refresh_studies()
    window.starter_combo.setCurrentIndex(window.starter_combo.findData(identifier))
    choose_material('remix'); window.new_piece_button.click()
    assert window.composition == original
    assert window.current_canvas() == original['canvas']
    assert window.composer.fps.value() == 12 and window.document_path is None
    window.composer.effects_panel.toggle_bypass('tape')
    path = tmp_path / 'remixed.json'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(path), ''))
    assert window.save_sequence_dialog()
    assert study_composition(identifier) == original
    assert load_composition(path) != original


def test_cancel_video_picker_preserves_current_piece(make_window, monkeypatch):
    window = make_window()
    window.composer.fps.setValue(12); window.play.setChecked(True)
    before = copy.deepcopy(window.document_state()); identity = window.document_identity
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args: ('', ''))
    choose_material('video'); window.new_piece_button.click()
    assert window.document_state() == before and window.document_identity is identity
    assert window.play_timer.isActive() and window.import_job is None


def test_video_choice_imports_native_canvas_treats_and_reopens(make_window, clip, tmp_path, monkeypatch):
    window = make_window()
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args: (clip['path'], ''))
    choose_material('video'); window.new_piece_action.trigger()
    wait_until(lambda: window.import_job is None)
    assert window.composition['footage']['path'] == clip['path']
    assert (window.current_canvas()['width'], window.current_canvas()['height']) == (128, 96)
    assert window.sequence['fps'] == 12 and window.sequence['duration'] == 1
    assert window.composer.look_tabs.currentWidget() is window.composer.video_panel
    window.composer.effects_panel.add_effect('tape', 0)
    treated = copy.deepcopy(window.composition)
    path = tmp_path / 'video-piece.json'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(path), ''))
    assert window.save_sequence_dialog()
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args: (str(path), ''))
    window.load_sequence_dialog()
    assert window.composition == treated == load_composition(path)
    assert not window.has_unsaved_changes()
