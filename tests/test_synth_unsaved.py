"""Close decisions protect authored documents and unapplied text."""
import copy
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QApplication, QFileDialog, QInputDialog, QMessageBox

import synth_studio
from synth import curated_presets, load_synth, save_synth
from synth_composition import load_composition, save_composition
from synth_sequence import load_sequence, reference_sequence, save_sequence
from synth_studio import SynthStudio


@pytest.fixture
def make_window(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(SynthStudio, 'request_frame', lambda self: None)
    windows = []

    def make(mode='composition'):
        kwargs = {}
        if mode == 'sequence': kwargs['sequence'] = reference_sequence()
        if mode == 'preset': kwargs['preset'] = curated_presets()['Reference blinds']
        window = SynthStudio(**kwargs)
        windows.append(window)
        window.show(); app.processEvents()
        return window

    yield make
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: QMessageBox.StandardButton.Discard)
    for window in windows: window.close()
    QThreadPool.globalInstance().waitForDone(10000)
    app.processEvents()


def edit(window):
    if window.composition is not None:
        window.composer.duration.setValue(window.sequence['duration'] + 1)
    elif window.sequence is not None:
        window.sequence_field_controls['duration'].setValue(window.sequence['duration'] + 1)
    else:
        window.global_controls['seed'].setValue(window.preset['seed'] + 1)


@pytest.mark.parametrize('mode', ['composition', 'sequence', 'preset'])
def test_clean_close_needs_no_warning(make_window, monkeypatch, mode):
    window = make_window(mode)
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: pytest.fail('Clean document prompted'))
    assert not window.has_unsaved_changes()
    assert window.close()
    assert window.closing


@pytest.mark.parametrize('mode', ['composition', 'sequence', 'preset'])
def test_cancel_keeps_document_preview_and_sources_running(make_window, monkeypatch, mode):
    window = make_window(mode); edit(window)
    window.play.setChecked(True)
    original = copy.deepcopy(window.document_state())
    prompts = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: prompts.append(args) or QMessageBox.StandardButton.Cancel)
    assert not window.close()
    assert window.isVisible() and not window.closing and window.play_timer.isActive()
    assert not window.video_frames.cancel.event.is_set()
    assert window.document_state() == original
    assert prompts[0][3] == (QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
    assert prompts[0][4] == QMessageBox.StandardButton.Cancel


def test_discard_closes_without_saving(make_window, monkeypatch):
    window = make_window(); edit(window)
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: QMessageBox.StandardButton.Discard)
    monkeypatch.setattr(window, 'save_sequence_dialog', lambda: pytest.fail('Discard tried saving'))
    assert window.close() and window.closing
    assert window.video_frames.cancel.event.is_set()


@pytest.mark.parametrize('mode,loader', [('composition', load_composition), ('sequence', load_sequence), ('preset', load_synth)])
def test_save_on_close_writes_the_active_document(make_window, monkeypatch, tmp_path, mode, loader):
    window = make_window(mode); edit(window)
    path = tmp_path / f'{mode}.json'
    original = copy.deepcopy(window.document_state()[1])
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: QMessageBox.StandardButton.Save)
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(path), ''))
    assert window.close()
    assert loader(path) == original
    assert not window.has_unsaved_changes()


def test_cancel_save_dialog_keeps_window_dirty(make_window, monkeypatch):
    window = make_window(); edit(window)
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: QMessageBox.StandardButton.Save)
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: ('', ''))
    assert not window.close()
    assert window.has_unsaved_changes() and window.isVisible() and not window.closing
    assert not window.video_frames.cancel.event.is_set()


@pytest.mark.parametrize('mode,writer', [('composition', 'save_composition'), ('sequence', 'save_sequence'), ('preset', 'save_synth')])
def test_write_failure_keeps_window_and_baseline(make_window, monkeypatch, tmp_path, mode, writer):
    window = make_window(mode); edit(window)
    baseline = copy.deepcopy(window.clean_document)
    errors = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: QMessageBox.StandardButton.Save)
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(tmp_path / 'document.json'), ''))
    monkeypatch.setattr(QMessageBox, 'critical', lambda *args: errors.append(args[2]))

    def fail(*args): raise OSError('Disk full')

    monkeypatch.setattr(synth_studio, writer, fail)
    assert not window.close()
    assert window.isVisible() and not window.closing and window.has_unsaved_changes()
    assert window.clean_document == baseline
    assert not window.video_frames.cancel.event.is_set()
    assert errors == ['Disk full']


def test_undo_returns_to_clean_saved_content(make_window, monkeypatch, tmp_path):
    window = make_window(); edit(window)
    assert window.has_unsaved_changes()
    window.undo_composition(); assert not window.has_unsaved_changes()
    window.redo_composition()
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(tmp_path / 'document.json'), ''))
    assert window.save_sequence_dialog()
    assert not window.has_unsaved_changes()
    edit(window); assert window.has_unsaved_changes()
    window.undo_composition(); assert not window.has_unsaved_changes()
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: pytest.fail('Undo-to-save prompted'))
    assert window.close()


@pytest.mark.parametrize('mode,writer', [('composition', save_composition), ('sequence', save_sequence), ('preset', save_synth)])
def test_explicit_load_establishes_clean_baseline(make_window, monkeypatch, tmp_path, mode, writer):
    window = make_window(mode)
    path = tmp_path / f'{mode}.json'
    writer(path, window.document_state()[1])
    edit(window); assert window.has_unsaved_changes()
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args: (str(path), ''))
    if mode == 'preset': window.load_preset_dialog()
    else: window.load_sequence_dialog()
    assert not window.has_unsaved_changes()


def test_study_selection_establishes_clean_baseline(make_window):
    window = make_window(); edit(window)
    window.load_starter_id('text-transmission')
    assert not window.has_unsaved_changes()


@pytest.mark.parametrize('later_edit', [False, True])
def test_study_save_marks_only_its_saved_snapshot_clean(make_window, monkeypatch, later_edit):
    window = make_window(); edit(window)
    monkeypatch.setattr(QInputDialog, 'getText', lambda *args, **kwargs: ('My study', True))
    monkeypatch.setattr(window.jobs, 'start', lambda job: None)
    window.save_study_dialog()
    job = window.study_job
    if later_edit: edit(window)
    window.study_saved(job, 'personal:test')
    assert window.has_unsaved_changes() is later_edit
    if later_edit:
        window.undo_composition()
        assert not window.has_unsaved_changes()


def test_old_study_save_cannot_change_new_documents_baseline(make_window, monkeypatch):
    window = make_window(); edit(window)
    monkeypatch.setattr(QInputDialog, 'getText', lambda *args, **kwargs: ('My study', True))
    monkeypatch.setattr(window.jobs, 'start', lambda job: None)
    window.save_study_dialog(); job = window.study_job
    window.load_starter_id('text-transmission')
    baseline = copy.deepcopy(window.clean_document)
    window.study_saved(job, 'personal:test')
    assert window.clean_document == baseline and not window.has_unsaved_changes()


@pytest.mark.parametrize('save_fails', [False, True])
def test_study_save_completion_respects_newer_json_save_result(make_window, monkeypatch, tmp_path, save_fails):
    window = make_window(); edit(window)
    monkeypatch.setattr(QInputDialog, 'getText', lambda *args, **kwargs: ('My study', True))
    monkeypatch.setattr(window.jobs, 'start', lambda job: None)
    window.save_study_dialog(); job = window.study_job
    edit(window)
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(tmp_path / 'newer.json'), ''))
    if save_fails:
        def fail(*args): raise OSError('Disk full')
        monkeypatch.setattr(synth_studio, 'save_composition', fail)
        monkeypatch.setattr(QMessageBox, 'critical', lambda *args: None)
    assert window.save_sequence_dialog() is not save_fails
    baseline = copy.deepcopy(window.clean_document)
    window.study_saved(job, 'personal:test')
    if save_fails:
        assert window.clean_document == ('composition', job.project)
        assert window.has_unsaved_changes()
        window.undo_composition(); assert not window.has_unsaved_changes()
    else:
        assert window.clean_document == baseline and not window.has_unsaved_changes()


def test_focused_uncommitted_spin_edit_is_saved_on_close(make_window, monkeypatch, tmp_path):
    window = make_window()
    control = window.composer.duration
    previous = window.sequence['duration']
    control.setFocus(); QApplication.processEvents()
    control.lineEdit().setText(control.locale().toString(previous + 1, 'f', 2))
    assert window.sequence['duration'] == previous
    path = tmp_path / 'focused.json'
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: QMessageBox.StandardButton.Save)
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(path), ''))
    assert window.close()
    assert window.sequence['duration'] == previous + 1
    assert load_composition(path) == window.composition


def test_unapplied_text_is_saved_on_close(make_window, monkeypatch, tmp_path):
    window = make_window(); window.load_starter_id('text-transmission')
    control = window.composer.object_panel.controls['text.content'].input
    control.editor.setPlainText('A new phrase\nwith a second line')
    assert window.has_unsaved_changes()
    path = tmp_path / 'text.json'
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: QMessageBox.StandardButton.Save)
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(path), ''))
    assert window.close()
    assert load_composition(path)['effects']['text']['params']['text.content'] == 'A new phrase\nwith a second line'
    assert not window.has_unsaved_changes()


def test_invalid_unapplied_text_prevents_save_and_close(make_window, monkeypatch, tmp_path):
    window = make_window(); window.load_starter_id('text-transmission')
    control = window.composer.object_panel.controls['text.content'].input
    control.editor.setPlainText('x' * 513)
    original = copy.deepcopy(window.composition)
    path = tmp_path / 'invalid-text.json'; errors = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: QMessageBox.StandardButton.Save)
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(path), ''))
    monkeypatch.setattr(QMessageBox, 'critical', lambda *args: errors.append(args[2]))
    assert not window.close()
    assert window.isVisible() and not window.closing and window.has_unsaved_changes()
    assert window.composition == original and control.editor.toPlainText() == 'x' * 513
    assert not path.exists() and errors


@pytest.mark.parametrize('matching', [False, True])
def test_duplicate_text_drafts_are_saved_only_if_they_agree(make_window, monkeypatch, tmp_path, matching):
    window = make_window(); window.load_starter_id('text-transmission')
    window.composer.effects_panel.inspect_effect('text')
    object_control = window.composer.object_panel.controls['text.content'].input
    effect_control = window.composer.effects_panel.controls['text.content'].input
    object_control.editor.setPlainText('Object wording')
    effect_control.editor.setPlainText('Object wording' if matching else 'Effect wording')
    path = tmp_path / 'text.json'; errors = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: QMessageBox.StandardButton.Save)
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(path), ''))
    monkeypatch.setattr(QMessageBox, 'critical', lambda *args: errors.append(args[2]))
    assert window.close() is matching
    if matching:
        assert load_composition(path)['effects']['text']['params']['text.content'] == 'Object wording'
        assert not window.has_unsaved_changes()
    else:
        assert not path.exists() and errors and window.has_unsaved_changes()
        assert object_control.editor.toPlainText() == 'Object wording'
        assert effect_control.editor.toPlainText() == 'Effect wording'


@pytest.mark.parametrize('mode', ['composition', 'sequence', 'preset'])
def test_save_reuses_file_and_save_as_moves_identity(make_window, monkeypatch, tmp_path, mode):
    window = make_window(mode)
    first, second = tmp_path / 'first.json', tmp_path / 'second.json'
    paths = iter([first, second])
    calls = []
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: calls.append(args) or (str(next(paths)), ''))
    assert window.save_sequence_dialog() and window.document_path == first
    edit(window)
    assert window.save_sequence_dialog() and len(calls) == 1
    assert window.save_as_dialog() and window.document_path == second and len(calls) == 2
    assert first.exists() and second.exists() and not window.has_unsaved_changes()


@pytest.mark.parametrize('replacement', ['new', 'study', 'open', 'preset'])
def test_cancel_replacement_preserves_document_session(make_window, monkeypatch, tmp_path, replacement):
    window = make_window(); edit(window)
    path = tmp_path / 'saved.json'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(path), ''))
    assert window.save_sequence_dialog()
    edit(window)
    before = copy.deepcopy(window.composition)
    history = copy.deepcopy(window.undo_compositions)
    identity = window.document_identity
    generation = window.settings_generation
    window.play.setChecked(True)
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: QMessageBox.StandardButton.Cancel)
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args: (str(path), ''))
    if replacement == 'new': window.new_composition()
    elif replacement == 'study': window.load_starter_id('text-transmission')
    elif replacement == 'open': window.load_sequence_dialog()
    else: window.select_curated('Reference blinds')
    assert window.composition == before and window.undo_compositions == history
    assert window.document_identity is identity and window.document_path == path
    assert window.settings_generation == generation and window.play.isChecked()
    assert not window.video_frames.cancel.event.is_set()


def test_failed_atomic_replace_preserves_existing_file_and_path(make_window, monkeypatch, tmp_path):
    window = make_window()
    path = tmp_path / 'old.json'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(path), ''))
    assert window.save_sequence_dialog()
    previous = path.read_bytes(); edit(window)
    monkeypatch.setattr(QMessageBox, 'critical', lambda *args: None)
    def fail(*args): raise OSError('replace failed')
    monkeypatch.setattr(synth_studio.os, 'replace', fail)
    assert not window.save_sequence_dialog()
    assert path.read_bytes() == previous and window.document_path == path
    assert window.has_unsaved_changes() and list(tmp_path.iterdir()) == [path]


def test_title_tracks_drafts_undo_and_detailed_copy(make_window):
    window = make_window(); window.load_starter_id('text-transmission')
    initial = window.windowTitle()
    control = window.composer.object_panel.controls['text.content'].input
    control.editor.setPlainText('Draft wording')
    assert '*' in window.windowTitle() and '*' in window.document_title.text()
    control.editor.setPlainText(control.value())
    assert window.windowTitle() == initial
    edit(window); assert '*' in window.windowTitle()
    window.undo_composition(); assert window.windowTitle() == initial
    window.open_detailed_copy()
    detail = window.detail_windows[-1]
    assert 'detailed copy' in detail.windowTitle() and detail.document_path is None
    detail.close()


def test_import_final_replacement_checks_latest_edits_and_identity(make_window, monkeypatch):
    window = make_window()
    monkeypatch.setattr(window.jobs, 'start', lambda job: None)
    footage = {'path': '/tmp/video.mp4'}
    monkeypatch.setattr(synth_studio, 'video_composition', lambda _footage: copy.deepcopy(window.composition))
    window.start_video_import('/tmp/video.mp4'); job = window.import_job
    edit(window); before = copy.deepcopy(window.composition)
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: QMessageBox.StandardButton.Cancel)
    window.video_imported(job, footage, False)
    assert window.composition == before
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: QMessageBox.StandardButton.Discard)
    window.start_video_import('/tmp/video.mp4'); old = window.import_job
    window.new_composition(); before = copy.deepcopy(window.composition)
    window.video_imported(old, footage, False)
    assert window.composition == before


@pytest.mark.parametrize('alias', [False, True])
def test_save_as_rejects_source_media_including_symlink_alias(make_window, monkeypatch, tmp_path, alias):
    window = make_window(); edit(window)
    source = tmp_path / 'source.mov'; source.write_bytes(b'original video bytes')
    window.sequence['footage'] = {'path': str(source)}
    target = source
    if alias:
        target = tmp_path / 'alias.json'; target.symlink_to(source)
    before = copy.deepcopy(window.composition); errors = []
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(target), ''))
    monkeypatch.setattr(QMessageBox, 'critical', lambda *args: errors.append(args[2]))
    assert not window.save_as_dialog()
    assert source.read_bytes() == b'original video bytes' and window.document_path is None
    assert window.composition == before and window.has_unsaved_changes() and errors


def test_save_rejects_bundled_resources_and_open_does_not_bind_them(make_window, monkeypatch):
    from pathlib import Path
    window = make_window()
    resource = Path(synth_studio.__file__).parent / 'presets/composite-study-15s.json'
    before = resource.read_bytes()
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args: (str(resource), ''))
    assert window.load_sequence_dialog() and window.document_path is None
    edit(window)
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(resource), ''))
    monkeypatch.setattr(QMessageBox, 'critical', lambda *args: None)
    assert not window.save_sequence_dialog() and resource.read_bytes() == before
    assert window.has_unsaved_changes()
