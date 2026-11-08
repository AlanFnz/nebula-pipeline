import copy
import time

import numpy as np
import pytest

from synth_lattice_sound import color_wave_sound, color_notes
from synth_live_midi import MidiPlan, MidiEngine, LiveMidiMonitor, midi_pitch


def source():
    c = color_wave_sound(); c.update(enabled=True, seamless_loop=True)
    t = np.linspace(0, 2, 201)
    s = dict(time=t, presence=np.ones_like(t), expansion=t/2, motion=t/2,
             lattice_phase_0=t/2, lattice_area_0=np.ones_like(t), lattice_radius=t/2)
    return dict(duration=2), s, c


def test_visual_attacks_and_tuning_are_preserved():
    seq, sig, c = source(); before=copy.deepcopy(c)
    p = MidiPlan(seq, sig, c)
    authored = color_notes(sig,c)
    assert len(p.notes) == len(authored)
    for n, original in zip(p.notes, authored):
        v = c['voices'][original['voice']]
        assert n.start == original['time']
        assert n.pitch == midi_pitch(v['pitch']*2**(original['semitones']/12))[0]
    assert c == before


def test_pad_chord_sub_and_wave_stay_on_across_wrap_and_seek():
    seq, sig, c = source()
    c['pad'].update(enabled=True,follow_root=False,pitch=82.406889,octave=2,harmony='minor9')
    c['choir'].update(enabled=True,octave=0)
    c['sub'].update(enabled=True,octaves_below=4)
    c['wave']['enabled']=True
    p = MidiPlan(seq,sig,c)
    assert [n for ch,n,_ in p.sustained if ch==2] == [64,71,79,86,90]
    assert (5,16) in p.active(.5)  # E0, without octave-name ambiguity.
    for at in (0.,1.999,2.,7.7):
        assert all((ch,n) in p.active(at) for ch,n,_ in p.sustained)
    assert any(m[0]==0xE6 for m in p.controls(.7))


def test_solo_mute_and_disabled_do_not_leak_notes():
    seq,sig,c=source(); c['pad']['enabled']=True
    c['mixer']['pad']['solo']=True
    p=MidiPlan(seq,sig,c)
    assert not p.notes and p.sustained
    c['mixer']['pad']['mute']=True
    assert not MidiPlan(seq,sig,c).active(.1)
    c['enabled']=False
    assert not MidiPlan(seq,sig,c).active(.1)


class Port:
    def __init__(self): self.messages=[];self.closed=False
    def send(self,m): self.messages.append((time.monotonic(),m))
    def close(self): self.closed=True


def wait_for(predicate):
    until=time.monotonic()+2
    while not predicate() and time.monotonic()<until: time.sleep(.005)
    assert predicate()


def test_worker_receives_play_stop_seek_and_closes_with_no_hanging_notes():
    seq,sig,c=source();c['pad']['enabled']=True
    port=Port();errors=[]
    engine=MidiEngine(errors.append,lambda _:None,output_factory=lambda:port)
    try:
        engine.command('source',seq,sig,c)
        engine.command('start',0.,time.monotonic())
        wait_for(lambda:any(m[0]&0xF0==0x90 for _,m in port.messages))
        engine.command('stop')
        wait_for(lambda:any(m[:2]==(0xB2,123) for _,m in port.messages))
        engine.command('start',1.,time.monotonic())
        wait_for(lambda:sum(m[0]==0x92 for _,m in port.messages)>=4)
    finally:engine.close()
    assert not errors and port.closed and not engine.thread.is_alive()
    assert port.messages[-1][1] == (0xB6,120,0)


def test_monitor_loop_does_not_retrigger_pad():
    seq,sig,c=source(); clock=[1.];port=Port()
    monitor=LiveMidiMonitor(output_factory=lambda:port,clock=lambda:clock[0])
    try:
        monitor.set_source(seq,sig,c);monitor.sync(1.9,True)
        anchor=monitor.anchor;clock[0]+=.2;monitor.sync(.1,True,force=True)
        assert monitor.anchor==anchor
        monitor.sync(.8,True,force=True)
        assert monitor.seconds==.8
        monitor.set_monitor(.7,True);assert not monitor.playing
    finally:monitor.close()
