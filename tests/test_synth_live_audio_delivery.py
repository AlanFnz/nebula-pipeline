"""Live edits must preserve samples and keep feeding audio during GUI stalls."""
import copy
import threading
import time

import numpy as np
import pytest

from synth_visual_sound import RATE, _smooth, instrument_sound
from synth_visual_sound_instrument import InstrumentVoice, instrument_controls, instrument_note_duration, note_envelope
from synth_visual_sound_live import BLOCK, LiveInstrument
from test_synth_visual_sound_instrument import signals
from test_synth_visual_sound_live import Output, monitors
from test_synth_visual_sound_ui import app, studio
from test_synth_composer_ui import wait_until


@pytest.mark.parametrize('mode', ['visual', 'sequence'])
@pytest.mark.parametrize('attack,release', [(.008,.02), (.01848,.41981), (.18,.9)])
def test_windowed_envelopes_preserve_complete_controls(mode,attack,release):
    config=instrument_sound();config.update(arp_mode=mode,attack=attack,release=release)
    if mode=='sequence': config.update(sequence_trigger='loop',bpm=137.,sequence_length=16,subdivision='1/16')
    s=signals(20.);s['opening'][20::53]=1
    notes,actual=instrument_controls(s,config)
    expected=np.zeros_like(s['time'])
    for note in notes:
        expected=np.maximum(expected,note_envelope(s['time']-note['time'],instrument_note_duration(note,config),attack,release))
    assert np.array_equal(actual,_smooth(expected,.035))


def test_envelope_work_is_limited_to_note_lifetimes(monkeypatch):
    import synth_visual_sound_instrument as instrument
    config=instrument_sound();config.update(arp_mode='sequence',sequence_trigger='loop',bpm=160.,subdivision='1/16')
    s=signals(20.);sizes=[];original=instrument.note_envelope
    def measured(age,*args): sizes.append(len(age));return original(age,*args)
    monkeypatch.setattr(instrument,'note_envelope',measured)
    notes,_=instrument_controls(s,config)
    assert len(sizes)==len(notes) and max(sizes)<len(s['time'])/10


def test_live_wave_reuse_is_exact_through_articulation_and_oscillator_edits(monkeypatch):
    s=signals(2.);c=instrument_sound();c.update(arp_mode='sequence',sequence_trigger='loop',subdivision='1/16')
    c['mixer']['arpeggio'].update(low_db=-8.46,mid_db=-1.29,high_db=5.98)
    seq=dict(duration=2.,seed=72)
    updates={20:dict(attack=.01848,release=.41981),35:dict(opening=.87),50:dict(detune=21.),65:dict(arp_pitch=320.),80:dict(unison=5)}
    def render():
        engine=LiveInstrument(seq,s,c);out=[];config=copy.deepcopy(c)
        for i in range(100):
            if i in updates: config.update(updates[i]);engine.update(config)
            out.append(engine.render())
        return np.concatenate(out)
    actual=render();original=InstrumentVoice.render
    monkeypatch.setattr(InstrumentVoice,'render',lambda self,start,length,**kw:original(self,start,length))
    assert np.array_equal(actual,render())


class PacedOutput(Output):
    def __init__(self,parent):
        super().__init__(parent);self.calls=[];self.mark('create');self.sent=0;self.started=0
    def mark(self,kind): self.calls.append((kind,threading.get_ident()))
    def start(self):
        self.mark('start');super().start();self.sent=0;self.started=time.monotonic()
    def volume(self,value): self.mark('volume');super().volume(value)
    def write(self,packet):
        self.mark('write')
        capacity=max(0,round((time.monotonic()-self.started+.04)*RATE)*8-self.sent)
        data=packet[:capacity//8*8];self.sent+=len(data)
        return super().write(data)
    def stop(self): self.mark('stop');super().stop()
    def close(self): self.mark('close');super().close()


def test_audio_device_keeps_running_while_gui_cannot_process_events(monitors):
    monitor=monitors(backend_factory=PacedOutput);c=instrument_sound();c['unison']=1
    monitor.set_source(dict(duration=3.,seed=1),signals(3.),c);monitor.sync(0.,True)
    wait_until(lambda:monitor.backend is not None and len(monitor.backend.audio)>RATE*8*.08)
    output=monitor.backend;before=len(output.audio)
    # No processEvents/QTest here: the GUI is intentionally unavailable for
    # longer than both audio buffers combined, as during a native window stall.
    time.sleep(.25)
    assert len(output.audio)-before>RATE*8*.15
    monitor.set_monitor(.2,True);wait_until(lambda:output.level==0)
    monitor.close()
    owners={thread for _,thread in output.calls}
    assert len(owners)==1 and threading.get_ident() not in owners
    assert {'create','start','volume','write','stop','close'}<={kind for kind,_ in output.calls}
    assert not monitor.output_thread.isRunning() and not monitor.producer.thread.is_alive()


def test_latest_edits_seek_and_delayed_failure_do_not_reset_new_stream(monitors):
    monitor=monitors(backend_factory=PacedOutput);c=instrument_sound()
    monitor.set_source(dict(duration=3.,seed=1),signals(3.),c);monitor.sync(0.,True)
    wait_until(lambda:monitor.backend is not None and len(monitor.backend.audio)>BLOCK*8)
    old_epoch=monitor.epoch;producer_epoch=monitor.producer.epoch
    for i in range(50):
        c['opening']=i/50;monitor.set_config(c)
    monitor.sync(1.5,True);c['release']=.7;monitor.set_config(c)
    wait_until(lambda:monitor.backend.starts==2 and monitor.producer.command[2]['release']==.7)
    monitor.output_failed(old_epoch,'Old device failure')
    monitor.producerFailed.emit(producer_epoch,'Old synth failure')
    wait_until(lambda:monitor.producer.command[2]['opening']==.98)
    assert not monitor.unavailable and monitor.playing
    monitor.sync(1.5,False);wait_until(lambda:not monitor.output.playing)
    count=len(monitor.backend.audio);time.sleep(.05)
    assert len(monitor.backend.audio)==count and not monitor.output.pending


def test_audio_device_failure_stops_safely_and_new_source_can_retry(monitors):
    class Broken(Output):
        broken=True
        def write(self,packet):
            if self.broken: raise RuntimeError('Disconnected test output')
            return super().write(packet)
    monitor=monitors(backend_factory=Broken);c=instrument_sound();seq=dict(duration=3.,seed=1);s=signals(3.)
    monitor.set_source(seq,s,c);monitor.sync(0.,True)
    wait_until(lambda:monitor.unavailable)
    assert not monitor.playing
    monitor.backend.broken=False;monitor.set_source(seq,s,c);monitor.sync(.5,True)
    wait_until(lambda:len(monitor.backend.audio)>BLOCK*8)
    assert not monitor.unavailable and monitor.playing


def test_sound_edits_reuse_visual_hash_but_document_revisions_invalidate_it(studio,monkeypatch):
    import synth_visual_sound_live
    import synth_preview
    from synth_visual_sound_live import LiveSoundMonitor
    class Monitor(LiveSoundMonitor):
        def __init__(self,parent):super().__init__(parent,backend_factory=Output)
    monkeypatch.setattr(synth_visual_sound_live,'LiveSoundMonitor',Monitor)
    calls=[];original=synth_preview._visual_document
    def measured(seq):calls.append(seq);return original(seq)
    monkeypatch.setattr(synth_preview,'_visual_document',measured)
    studio.apply_visual_sound(instrument_sound());studio.open_visual_sound()
    wait_until(lambda:studio.live_signals is not None,seconds=15)
    calls.clear();job_signals=studio.live_signals
    for i in range(15):
        c=instrument_sound();c['attack']=.01+i*.001;studio.audition_visual_sound(c)
    assert calls==[] and studio.live_signals is job_signals
    studio.settings_generation+=1;studio.audition_visual_sound(c)
    assert len(calls)==1 and studio.live_signals is job_signals # unchanged pixels, no analysis restart
    studio.sequence['seed']+=1;studio.settings_generation+=1;studio.audition_visual_sound(c)
    assert len(calls)==2 and studio.live_signals is None
    studio.visual_sound_dialog.close()
