import copy
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from synth_performance import defaults, values_at, source_time
from synth_sequence import render_sequence_frame
from synth_visual_sound import instrument_sound, RATE
from synth_visual_sound_live import LiveInstrument, BLOCK
from test_synth_full_preview import window, setup_full, settle, prepared
from test_synth_visual_sound_ui import app, studio
from test_synth_visual_sound_instrument import signals


def test_fast_controls_reuse_all_pixels_and_export_the_displayed_result(window, monkeypatch):
    monkeypatch.setattr(window,'preview_size',lambda:(96,72))
    setup_full(window);window.prepare_full_playback();prepared(window)
    count=window.timeline.maximum()+1
    cache=window.preview_frames;generation=window.settings_generation
    original={i:cache.get(i) for i in range(count)}
    window.begin_performance_gesture()
    for value in (110,120,135):window.edit_performance('scale',value)
    window.end_performance_gesture();QTest.qWait(60);settle(window)
    assert window.settings_generation==generation and cache.complete(count)
    assert original=={i:cache.get(i) for i in range(count)}
    for frame in (0,3,count-1):
        window.timeline.setValue(frame);settle(window)
        assert window.viewer.packet[1]==render_sequence_frame(window.sequence,frame/window.preview_fps(),(96,72)).tobytes()
    window.undo_composition();settle(window)
    assert 'visual_performance' not in window.composition
    assert cache.complete(count)
    window.redo_composition();settle(window)
    assert window.composition['visual_performance']['values']['scale']==135
    assert cache.complete(count)


def test_pace_selects_prepared_source_frame_without_changing_timeline(window,monkeypatch):
    monkeypatch.setattr(window,'preview_size',lambda:(96,72))
    setup_full(window);window.prepare_full_playback();prepared(window)
    duration=window.sequence['duration']; fps=window.preview_fps();generation=window.settings_generation
    window.edit_performance('pace',200);QTest.qWait(60);settle(window)
    window.timeline.setValue(3);settle(window)
    assert window.current_time==3/fps
    assert window.viewer.packet==window.preview_frames.get(6)
    assert window.sequence['duration']==duration and window.settings_generation==generation
    assert not window.render_running


def test_recording_replays_and_undoes_as_one_take(studio):
    before=copy.deepcopy(studio.composition);undos=len(studio.undo_compositions)
    studio.play.setChecked(True);studio.play_timer.stop()
    studio.set_performance_recording(True)
    studio.current_time=1.;studio.edit_performance('rotation',25)
    studio.current_time=2.;studio.edit_performance('rotation',60)
    studio.current_time=3.;studio.edit_performance('scale',120)
    studio.play.setChecked(False)
    config=studio.composition['visual_performance']
    assert not studio.performance_recording
    assert values_at(config,2,studio.sequence['duration'])['rotation']==60
    assert len(studio.undo_compositions)==undos+1
    studio.undo_composition();assert studio.composition==before
    studio.redo_composition();assert studio.composition['visual_performance']==config
    studio.edit_performance('rotation',10)
    assert 'rotation' not in studio.composition['visual_performance']['tracks']


def test_inspector_and_sound_panel_share_values_and_separate_undo(studio,monkeypatch):
    monkeypatch.setattr(studio,'audition_visual_sound',lambda *_:None)
    studio.open_visual_sound();dialog=studio.visual_sound_dialog
    dialog.pitch.setValue(200);draft=dialog.read_config()
    dialog.tabs.setCurrentIndex(dialog.performance_tab)
    dialog.performance_panel.knobs['twist'].setValue(40);QTest.qWait(60)
    assert studio.performance_panel.knobs['twist'].value()==40
    dialog.request_undo()
    assert 'visual_performance' not in studio.composition
    assert dialog.read_config()==draft
    dialog.request_redo()
    assert studio.composition['visual_performance']['values']['twist']==40
    dialog.tabs.setCurrentIndex(0);dialog.request_undo()
    assert dialog.pitch.value()!=200
    assert studio.composition['visual_performance']['values']['twist']==40


def test_live_visual_changes_crossfade_without_stopping_audio():
    seq=dict(duration=3.,seed=45); config=instrument_sound(); original=signals(3.)
    live=LiveInstrument(seq,original,config); first=live.render(RATE)
    changed={k:v.copy() for k,v in original.items()};changed['motion'][:]=1;changed['expansion'][:]=1
    live.update(config,changed,seq)
    output=np.concatenate([first[-BLOCK:],*[live.render() for _ in range(8)]])
    assert live.position==RATE+8*BLOCK
    assert live.voice.signals is changed and live.old is None
    assert np.isfinite(output).all() and np.max(abs(np.diff(output,axis=0)))<.1


def test_keyboard_undo_from_visual_number_field(window):
    from PySide6.QtGui import QKeySequence
    window.composer.look_tabs.setCurrentWidget(window.performance_panel)
    assert window.composer.scope_combo.isHidden()
    assert window.composer.reset_label()=='' and window.reset_controls_button.isHidden()
    knob=window.performance_panel.knobs['rotation']
    knob.setValue(25);QTest.qWait(60)
    window.activateWindow();knob.number.setFocus();QTest.qWait(50)
    QTest.keySequence(knob.number,QKeySequence(QKeySequence.StandardKey.Undo))
    assert 'visual_performance' not in window.composition
    assert knob.value()==0
    QTest.keySequence(knob.number,QKeySequence(QKeySequence.StandardKey.Redo))
    assert window.composition['visual_performance']['values']['rotation']==25


def test_surface_changes_invalidate_pixels_but_preserve_playback_clock(studio):
    studio.play.setChecked(True);studio.play_timer.stop()
    generation=studio.settings_generation;anchor=studio.play_started
    studio.edit_performance('opening',25)
    studio.performance_timer.stop();studio.flush_performance()
    assert studio.settings_generation==generation+1
    assert studio.play_started==anchor and studio.play.isChecked()
    studio.play.setChecked(False)


def test_fast_edits_keep_the_analyzed_source(studio,monkeypatch):
    import synth_visual_sound_live
    import synth_preview
    from synth_visual_sound_live import LiveSoundMonitor
    from test_synth_visual_sound_live import Output
    from test_synth_composer_ui import wait_until
    class Monitor(LiveSoundMonitor):
        def __init__(self,parent):super().__init__(parent,backend_factory=Output)
    monkeypatch.setattr(synth_visual_sound_live,'LiveSoundMonitor',Monitor)
    studio.apply_visual_sound(instrument_sound());studio.open_visual_sound()
    wait_until(lambda:studio.live_signals is not None,seconds=15)
    base=studio.live_base_signals;epoch=studio.live_sound.epoch;calls=[]
    original=synth_preview._visual_document
    def measured(seq):calls.append(seq);return original(seq)
    monkeypatch.setattr(synth_preview,'_visual_document',measured)
    studio.begin_performance_gesture()
    for value in (105,110,125):
        studio.edit_performance('scale',value);studio.performance_timer.stop();studio.flush_performance()
    studio.end_performance_gesture()
    assert calls==[] and studio.live_base_signals is base
    assert studio.live_signals_job is None and studio.live_sound.epoch==epoch
    studio.visual_sound_dialog.close()
