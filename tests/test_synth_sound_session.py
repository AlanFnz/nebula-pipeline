"""Audition, applied project audio and a successfully saved file are distinct."""
import copy
import json
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
from synth_pleated_recipes import pleated_composition
from synth_studio import SynthStudio
from synth_visual_sound import instrument_sound
from synth_visual_sound_ui import VisualSoundDialog


@pytest.fixture
def editor(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(SynthStudio, 'request_frame', lambda *_: None)
    monkeypatch.setattr(SynthStudio, 'schedule_auto_preparation', lambda *_: None)
    monkeypatch.setattr(SynthStudio, 'prepare_visual_sound', lambda *_: None)
    monkeypatch.setattr(SynthStudio, 'audition_visual_sound', lambda self, config: setattr(self, 'live_draft', copy.deepcopy(config)))
    project = pleated_composition();project['generated_sound'] = instrument_sound()
    window = SynthStudio(composition=project)
    window.auto_prepare.setChecked(False);window.visual_sound_debounce.stop()
    window.document_path = tmp_path / 'sound.json'
    assert window.save_sequence_dialog()
    window.open_visual_sound();app.processEvents()
    yield window, window.visual_sound_dialog, app
    window.close();QThreadPool.globalInstance().waitForDone(5000);app.processEvents()


def test_draft_apply_save_undo_and_monitor_states(editor):
    window, dialog, _ = editor
    original = copy.deepcopy(window.composition)
    assert dialog.context_title.text() == original['name']
    assert dialog.sound_state.text() == 'Sound: Applied'
    assert dialog.file_state.text() == 'File: Saved'
    assert not dialog.apply_button.isEnabled()
    dialog.volume.setValue(35);dialog.mute.setChecked(True)
    assert not dialog.has_sound_draft() and not window.has_unsaved_changes()
    assert 'Monitor muted' in dialog.preview_source.text()
    dialog.mute.setChecked(False);dialog.opening.setValue(85)
    assert dialog.has_sound_draft() and 'Draft sound' in dialog.preview_source.text()
    assert dialog.file_state.text() == 'File: Saved'  # Only the editor has changed.
    assert window.composition == original
    dialog.apply()
    assert not dialog.has_sound_draft() and not dialog.apply_button.isEnabled()
    assert window.composition['generated_sound']['opening'] == .85
    assert dialog.file_state.text() == 'File: Unsaved changes'
    assert 'Applied sound' in dialog.preview_source.text()
    dialog.save_project_button.click()
    assert dialog.file_state.text() == 'File: Saved'
    assert json.loads(window.document_path.read_text())['generated_sound']['opening'] == .85
    window.undo_composition()
    assert window.composition == original and not dialog.has_sound_draft()
    assert dialog.file_state.text() == 'File: Unsaved changes'


def test_output_label_matches_actual_applied_route_when_not_live(editor):
    window, dialog, _ = editor
    dialog.opening.setValue(85);dialog.live.setChecked(False)
    assert dialog.has_sound_draft() and 'Applied sound' in dialog.preview_source.text()
    dialog.output.setCurrentIndex(dialog.output.findData('existing'))
    assert 'Applied sound' in dialog.preview_source.text()
    dialog.apply()
    assert 'Existing soundtrack / footage' in dialog.preview_source.text()
    assert not dialog.volume.isEnabled() and not dialog.mute.isEnabled()
    dialog.output.setCurrentIndex(dialog.output.findData('silent'));dialog.apply()
    assert dialog.preview_source.text() == 'Preview: Silent'


def test_midi_is_a_session_route_without_changing_saved_study(editor):
    from synth_lattice_sound import color_wave_sound
    window, dialog, _ = editor
    config = color_wave_sound(); config['enabled'] = True
    window.composition['generated_sound'] = config
    dialog.set_config(config)
    window.save_sequence_dialog()
    original = copy.deepcopy(window.composition)
    saved = window.document_path.read_bytes()
    dialog.midi.setChecked(True)
    assert window.uses_midi(config) and window.wants_live_sound(config)
    assert 'MIDI → Nebula Visuals' in dialog.preview_source.text()
    assert not dialog.volume.isEnabled() and not dialog.live.isEnabled()
    assert dialog.midi_panic.isEnabled()
    assert dialog.midi_refresh.isEnabled()
    requested = []
    dialog.midiRefreshRequested.connect(lambda: requested.append(True))
    dialog.midi_refresh.click()
    assert requested == [True]
    assert not dialog.has_sound_draft() and not window.has_unsaved_changes()
    assert window.composition == original and window.document_path.read_bytes() == saved
    dialog.midi.setChecked(False)
    assert dialog.volume.isEnabled() and dialog.live.isEnabled()
    assert not dialog.midi_refresh.isEnabled()
    assert not window.uses_midi(config)
    dialog.midi.setChecked(True)
    window.reset_visual_sound()
    assert not window.midi_monitor_enabled and not dialog.midi.isChecked()


@pytest.mark.parametrize('choice', ['apply', 'discard', 'cancel'])
def test_save_resolves_draft_without_silently_choosing_sound(editor, monkeypatch, choice):
    window, dialog, _ = editor
    before = window.document_path.read_bytes()
    original = copy.deepcopy(window.composition['generated_sound'])
    dialog.opening.setValue(89)
    monkeypatch.setattr(dialog, 'choose_pending_sound', lambda *args: choice)
    assert window.save_sequence_dialog() is (choice != 'cancel')
    if choice == 'apply':
        assert json.loads(window.document_path.read_text())['generated_sound']['opening'] == .89
        assert not dialog.has_sound_draft()
    else:
        assert window.composition['generated_sound'] == original
        assert window.document_path.read_bytes() == before
        assert dialog.has_sound_draft()
    monkeypatch.setattr(dialog, 'choose_pending_sound', lambda *args: 'discard')


def test_failed_save_never_claims_file_is_saved(editor, monkeypatch):
    window, dialog, _ = editor
    original = window.document_path.read_bytes()
    dialog.opening.setValue(77);dialog.apply()
    def fail(*_): raise OSError('Disk full')
    monkeypatch.setattr('synth_studio.save_composition', fail)
    monkeypatch.setattr(QMessageBox, 'critical', lambda *_: None)
    assert not window.save_sequence_dialog()
    assert dialog.file_state.text() == 'File: Unsaved changes'
    assert dialog.sound_state.text() == 'Sound: Applied'
    assert window.document_path.read_bytes() == original


def test_close_cancel_then_discard_keeps_visual_edits(editor, monkeypatch):
    window, dialog, app = editor
    original_sound = copy.deepcopy(window.composition['generated_sound'])
    window.edit_performance('scale', 115)
    visual = copy.deepcopy(window.composition.get('visual_performance'))
    dialog.opening.setValue(92)
    monkeypatch.setattr(dialog, 'choose_pending_sound', lambda *args: 'cancel')
    dialog.close();app.processEvents()
    assert dialog.isVisible() and dialog.has_sound_draft()
    monkeypatch.setattr(dialog, 'choose_pending_sound', lambda *args: 'discard')
    dialog.close();app.processEvents()
    assert not dialog.isVisible()
    assert window.composition['generated_sound'] == original_sound
    assert window.composition.get('visual_performance') == visual
    assert window.has_unsaved_changes()


@pytest.mark.parametrize('choice', ['apply', 'discard', 'cancel'])
def test_export_uses_explicit_sound_choice(editor, monkeypatch, tmp_path, choice):
    window, dialog, _ = editor
    original = copy.deepcopy(window.composition['generated_sound'])
    dialog.opening.setValue(93)
    monkeypatch.setattr(dialog, 'choose_pending_sound', lambda *args: choice)
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *_: (str(tmp_path / 'export.mp4'), ''))
    jobs = []
    monkeypatch.setattr(window.jobs, 'start', lambda job, *args: jobs.append(job))
    window.export_dialog()
    assert bool(jobs) is (choice != 'cancel')
    if jobs:
        assert jobs[0].sequence['generated_sound'] == (dict(original, opening=.93) if choice == 'apply' else original)
        window.export_job = None;window.pending_jobs.remove(jobs[0])
    monkeypatch.setattr(dialog, 'choose_pending_sound', lambda *args: 'discard')


def test_read_only_visit_preserves_numeric_precision_and_render_recipe(editor):
    window, dialog, _ = editor
    config = copy.deepcopy(window.composition['generated_sound'])
    config['opening'] = .31857294
    window.apply_visual_sound(config)
    before = copy.deepcopy(window.composition);sequence = copy.deepcopy(window.sequence)
    dialog.set_config(config);window.refresh_sound_context()
    assert not dialog.has_sound_draft()
    dialog.set_playing(True);dialog.set_playing(False)
    dialog.tabs.setCurrentIndex(dialog.performance_tab)
    assert dialog.workspace_hint.text() == 'Visuals · All clips · Edits apply immediately'
    dialog.close()
    assert window.composition == before and window.sequence == sequence


def test_new_instrument_is_not_mistaken_for_applied_audio(editor):
    window, dialog, _ = editor
    document = copy.deepcopy(window.composition);document.pop('generated_sound')
    window.composer.commit(document, 'remove-sound')
    assert not dialog.applied_available and dialog.has_sound_draft()
    assert 'Draft sound' in dialog.preview_source.text()
    dialog.apply()
    assert dialog.applied_available and not dialog.has_sound_draft()
