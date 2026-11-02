"""Live audio shares export DSP, changes mid-stream and keeps the video clock."""
import copy
import time
import numpy as np
from PySide6.QtTest import QSignalSpy,QTest
from synth_visual_sound import RATE,instrument_sound
from synth_visual_sound_instrument import InstrumentVoice
from synth_visual_sound_live import BLOCK,FADE,LiveInstrument,LiveSoundMonitor,AudioProducer
from test_synth_visual_sound_instrument import signals
from test_synth_visual_sound_ui import app,studio
from test_synth_composer_ui import wait_until
from synth_visual_sound_ui import VisualSoundDialog


def test_live_static_blocks_are_identical_to_export():
    config=instrument_sound();seq=dict(duration=1.,seed=45);s=signals(1.)
    expected=InstrumentVoice(seq,config,s).render(0,RATE)
    voice=LiveInstrument(seq,s,config)
    result=np.concatenate([voice.render() for _ in range(RATE//BLOCK)])
    assert np.array_equal(expected,result)


def test_knob_changes_crossfade_without_restarting_the_clock_or_clicking():
    c=instrument_sound();seq=dict(duration=3.,seed=45);s=signals(3.)
    live=LiveInstrument(seq,s,c)
    first=live.render(RATE)
    changed=copy.deepcopy(c);changed.update(opening=.98,resonance=.99,pitch=392.,unison=5,detune=31.,density=1.)
    live.update(changed)
    pieces=[live.render() for _ in range(8)]
    audio=np.concatenate([first[-BLOCK:],*pieces])
    assert live.position==RATE+8*BLOCK and np.isfinite(audio).all()
    # At the update boundary, the previous voice continues exactly.
    steady=InstrumentVoice(seq,c,s);old=steady.render(0,RATE+BLOCK)
    assert pieces[0][0].tolist()==old[RATE].tolist()
    assert np.max(abs(np.diff(audio,axis=0)))<.10
    assert live.voice.config==changed and live.old is None
    live.update(c);live.render();live.update(changed)
    for _ in range(12): live.render()
    assert live.voice.config==changed


class Output:
    def __init__(self,parent): self.starts=0;self.audio=bytearray();self.level=1.;self.stops=0
    def start(self): self.starts+=1
    def stop(self): self.stops+=1
    def volume(self,value): self.level=value
    def write(self,packet): self.audio.extend(packet);return len(packet)
    def close(self): self.stop()


def test_live_monitor_updates_without_restarting_seeks_pauses_and_closes(app):
    clock=[10.];monitor=LiveSoundMonitor(backend_factory=Output,clock=lambda:clock[0])
    c=instrument_sound();monitor.set_source(dict(duration=3.,seed=1),signals(3.),c)
    monitor.sync(.4,True);wait_until(lambda:len(monitor.backend.audio)>BLOCK*8)
    output=monitor.backend;assert output.starts==1
    c['opening']=.9;monitor.set_config(c)
    clock[0]+=.08;monitor.sync(.48,True,force=True)
    assert output.starts==1 # GUI refreshes cannot reset the running stream.
    monitor.set_monitor(.3,True);assert output.level==0
    monitor.set_monitor(.3,False);assert output.level==.3
    monitor.sync(2.,True,force=True);assert output.starts==2
    monitor.sync(2.,False);assert not monitor.playing and not monitor.pending
    monitor.close();assert not monitor.producer.thread.is_alive()


def test_live_dialog_emits_drafts_without_applying_or_changing_monitor(app):
    d=VisualSoundDialog();d.set_config(instrument_sound());drafts=QSignalSpy(d.draftChanged);applied=QSignalSpy(d.configEdited)
    d.opening.setValue(80);d.resonance.setValue(90);QTest.qWait(50)
    assert drafts.count()==1 and applied.count()==0
    assert drafts.at(0)[0]['opening']==.8 and drafts.at(0)[0]['resonance']==.9
    d.volume.setValue(20);QTest.qWait(40);assert drafts.count()==1
    d.set_config(instrument_sound());QTest.qWait(40);assert drafts.count()==1
    d.apply();assert applied.count()==1
    d.close()


def test_studio_live_knobs_keep_transport_and_pixels_and_apply_is_undoable(studio,monkeypatch):
    import synth_visual_sound_live
    class Monitor(LiveSoundMonitor):
        def __init__(self,parent): super().__init__(parent,backend_factory=Output)
    monkeypatch.setattr(synth_visual_sound_live,'LiveSoundMonitor',Monitor)
    studio.apply_visual_sound(instrument_sound())
    studio.open_visual_sound();wait_until(lambda:studio.live_signals is not None,seconds=15)
    original=copy.deepcopy(studio.composition);generation=studio.settings_generation
    studio.play.setChecked(True);studio.play_timer.stop()
    monitor=studio.live_sound;clock=studio.play_started;worker=monitor.producer.thread
    studio.visual_sound_dialog.opening.setValue(95);QTest.qWait(70)
    assert studio.play.isChecked() and studio.play_started==clock
    assert studio.composition==original and studio.settings_generation==generation
    assert monitor.config['opening']==.95 and monitor.producer.thread is worker
    studio.visual_sound_dialog.apply()
    assert studio.composition['generated_sound']['opening']==.95
    assert studio.play_started==clock and studio.settings_generation==generation
    studio.play.setChecked(False);studio.undo_composition()
    assert studio.composition==original
    studio.visual_sound_dialog.close();assert not monitor.playing


def test_qt_audio_error_aliases_are_compared_by_value(app):
    # Some PySide versions expose distinct Error enum classes for QtAudio and QAudio.
    # They have identical values but compare unequal, even for NoError.
    from enum import Enum
    from synth_visual_sound_live import QtLiveOutput
    ForeignError=Enum('ForeignError',{'NoError':0})
    class Sink:
        def error(self): return ForeignError.NoError
        def bytesFree(self): return 16
    class IO:
        def write(self,data): return len(data)
    output=object.__new__(QtLiveOutput);output.sink=Sink();output.io=IO()
    assert output.write(b'a'*32)==16


def test_slow_device_initialization_catches_up_to_video_clock(app):
    clock=[10.]
    class SlowOutput(Output):
        def start(self): super().start();clock[0]+=.25
    monitor=LiveSoundMonitor(backend_factory=SlowOutput,clock=lambda:clock[0])
    monitor.set_source(dict(duration=3.,seed=1),signals(3.),instrument_sound())
    monitor.sync(1.,True)
    assert monitor.seconds==1.25 and monitor.anchor==10.25
    clock[0]+=.1;monitor.sync(1.35,True)
    assert monitor.backend.starts==1
    monitor.close()
