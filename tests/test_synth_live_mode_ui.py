"""Exercise the real Play path with a recording MIDI receiver, no DAW launch."""
import copy
import time

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QThreadPool, QSettings
from PySide6.QtWidgets import QApplication

from synth_composition import load_composition, save_composition
from synth_lattice_sound import color_wave_sound
from synth_live_midi import LiveMidiMonitor
from synth_live_mode import LIVE_OUTPUT, is_live
from synth_pleated_recipes import pleated_composition
from synth_studio import SynthStudio
from synth_visual_sound import instrument_sound
from test_synth_live_midi import Port


def settle(app, predicate, timeout=8):
    until = time.monotonic() + timeout
    while not predicate() and time.monotonic() < until:
        app.processEvents();time.sleep(.005)
    assert predicate()


@pytest.fixture
def live_editor(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    ports = []
    class RecordingMonitor(LiveMidiMonitor):
        def __init__(self, parent=None):
            port = Port();ports.append(port)
            super().__init__(parent, output_factory=lambda: port)
    monkeypatch.setattr('synth_live_midi.LiveMidiMonitor', RecordingMonitor)
    monkeypatch.setattr(SynthStudio, 'request_frame', lambda *_: None)
    monkeypatch.setattr(SynthStudio, 'schedule_auto_preparation', lambda *_: None)
    project = pleated_composition()
    project['generated_sound'] = dict(instrument_sound(), output=LIVE_OUTPUT)
    path = tmp_path / 'Live.json';save_composition(path, project)
    window = SynthStudio(composition=load_composition(path),settings=QSettings(str(tmp_path/'ui.ini'), QSettings.Format.IniFormat))
    window.document_path = path;window.auto_prepare.setChecked(False)
    settle(app, lambda: window.live_signals is not None)
    yield window, app, ports
    window.close();QThreadPool.globalInstance().waitForDone(5000)
    window.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()


def test_saved_live_plays_without_editor_and_close_keeps_notes(live_editor):
    w, app, ports = live_editor
    assert w.visual_sound_dialog is None and w.uses_midi()
    assert w.visual_sound_job is None and w.visual_sound_key is None
    assert w.visual_sound_button.text() == 'Live controls'
    w.play.setChecked(True)
    settle(app, lambda: any(m[0]&0xF0 == 0x90 for _,m in ports[-1].messages))
    monitor = w.live_sound
    w.open_visual_sound();app.processEvents()
    d = w.visual_sound_dialog
    assert d.windowTitle() == 'Ableton Live' and not d.has_sound_draft()
    assert d.voice.isHidden() and d.midi.isHidden() and d.gain.isHidden()
    assert not d.pitch.isHidden() and not d.opening.isHidden()
    assert not d.tabs.isTabVisible(1) and 'Live' in d.midi_hint.text()
    d.close();app.processEvents()
    assert w.live_sound is monitor and monitor.playing
    assert w.live_signals_job is None and w.visual_sound_job is None
    w.play.setChecked(False)
    settle(app, lambda: not monitor.playing)
    settle(app, lambda: any(m[:2] == (0xB0,123) for _,m in ports[-1].messages))


def test_mode_switch_undo_reload_and_old_study_are_isolated(live_editor, monkeypatch):
    w, app, ports = live_editor
    old = dict(instrument_sound(), output='silent')
    w.open_visual_sound();d = w.visual_sound_dialog
    original = copy.deepcopy(w.composition['generated_sound'])
    d.output.setCurrentIndex(d.output.findData('silent'));d.apply()
    assert not w.uses_midi() and w.visual_sound_button.text() == 'Synthesizer'
    assert not d.gain.isHidden() and d.tabs.isTabVisible(1)
    w.undo_composition()
    settle(app, lambda: w.uses_midi() and w.live_signals is not None)
    assert w.composition['generated_sound'] == original
    assert w.save_sequence_dialog()
    loaded = load_composition(w.document_path)
    monitor = w.live_sound
    w.set_composition(loaded, guard=False)
    settle(app, lambda: w.live_signals is not None and w.live_sound is not monitor)
    assert monitor.closed and is_live(w.composition['generated_sound'])
    project = copy.deepcopy(w.composition);project['generated_sound'] = old
    monitor = w.live_sound;w.set_composition(project, guard=False)
    assert monitor.closed and not w.uses_midi()
    assert w.composition['generated_sound'] == old


def test_failed_port_is_visible_never_falls_back_and_can_reconnect(live_editor, monkeypatch):
    w, app, ports = live_editor
    monitor = w.live_sound;monitor.fail('Test port unavailable')
    w.set_visual_sound_status('Live audition ready.')
    assert 'unavailable' in w.visual_sound_status and 'reconnect' in w.visual_sound_button.text()
    calls = []
    monkeypatch.setattr(w.visual_sound_player, 'sync', lambda *a, **k: calls.append(a))
    w.sync_visual_sound(1., True)
    assert not calls and not monitor.playing and w.visual_sound_job is None
    w.prepare_visual_sound()
    settle(app, lambda: w.live_sound is not monitor and w.live_signals_job is None)
    assert monitor.closed and not w.live_sound.unavailable
    assert w.uses_midi() and w.visual_sound_button.text() == 'Live controls'


def test_color_wave_live_controls_preserve_hidden_synth_settings(live_editor):
    w, app, _ = live_editor
    config = color_wave_sound();config['output'] = LIVE_OUTPUT
    w.apply_visual_sound(config);w.open_visual_sound();d = w.visual_sound_dialog
    baseline = copy.deepcopy(d.read_config())
    assert d.color_wave.level.isHidden()
    assert not d.color_wave.voices['strum']['pitch'].isHidden()
    assert not d.pad_space.pad['octave'].isHidden()
    assert d.pad_space.pad['cutoff'].isHidden()
    assert d.mixer.channels['body']['level_db'].isHidden()
    assert not d.mixer.channels['body']['mute'].isHidden()
    d.output.setCurrentIndex(d.output.findData('generated'))
    # Before the audition timer runs, verify the route is the only data edit.
    result = d.read_config();result['output'] = LIVE_OUTPUT
    assert result == baseline
    d.undo_draft()
    assert d.read_config() == baseline and d.color_wave.level.isHidden()


def test_unapplied_nonlive_destination_keeps_applied_midi(live_editor):
    w, app, _ = live_editor
    w.open_visual_sound();d = w.visual_sound_dialog
    d.output.setCurrentIndex(d.output.findData('existing'));d.emit_draft()
    assert w.uses_midi() and is_live(w.live_draft)
    assert 'MIDI →' in d.preview_source.text()
    assert d.has_sound_draft() and is_live(w.composition['generated_sound'])
    d.apply()
    assert not w.uses_midi() and not d.has_sound_draft()
    assert 'Existing soundtrack' in d.preview_source.text()
