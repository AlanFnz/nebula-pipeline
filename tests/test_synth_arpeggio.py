"""Independent melody tuning and finite, visually triggered phrase patterns."""
import copy
import numpy as np
import pytest
from PySide6.QtTest import QSignalSpy
from media import Cancellation
from synth_visual_sound import instrument_sound, normalize_sound, pcm_blocks
from synth_visual_sound_acid import gesture_notes, phrase_pattern
from synth_visual_sound_instrument import instrument_blocks
from synth_visual_sound_live import LiveInstrument
from synth_visual_sound_ui import VisualSoundDialog
from test_synth_visual_sound_instrument import signals
from test_synth_visual_sound_ui import app, studio
from test_synth_composer_ui import wait_until

NEW_FIELDS = ('arp_pitch', 'arp_notes', 'arp_steps', 'arp_pattern')


def render(config, s):
    return np.concatenate(list(pcm_blocks(dict(duration=s['time'][-1], seed=31, generated_sound=config), signals=s)))


def test_legacy_custom_root_and_original_phrases_keep_exact_pcm():
    legacy=instrument_sound();legacy['pitch']=217.9
    for key in NEW_FIELDS: legacy.pop(key)
    restored=normalize_sound(legacy)
    assert restored['arp_pitch']==legacy['pitch']
    s=signals(2.);s['opening'][15]=1
    expected=np.concatenate(list(instrument_blocks(dict(duration=2.,seed=31),legacy,s,Cancellation())))
    assert np.array_equal(render(restored,s),expected)
    s=signals(5.);s['opening'][[24,240]]=1
    original=gesture_notes(s,dict(legacy,version=2))
    assert gesture_notes(s,restored)==original


def test_body_and_arpeggio_pitch_are_independent_in_pcm():
    c=instrument_sound();s=signals(1.);s['opening'][12]=1
    c['connections']['body']['enabled']=False
    melody=render(c,s)
    c['pitch']=330.
    assert np.array_equal(melody,render(c,s))
    c['arp_pitch']=220.
    assert not np.array_equal(melody,render(c,s))
    c['connections']['body']['enabled']=True;c['connections']['arpeggio']['enabled']=False
    body=render(c,s)
    c['arp_pitch']=110.
    assert np.array_equal(body,render(c,s))
    c['pitch']=220.
    assert not np.array_equal(body,render(c,s))


@pytest.mark.parametrize('pattern,expected',[
    ('up',(0,1,2,0,1,2,0,1)),('down',(2,1,0,2,1,0,2,1)),
    ('up_down',(0,1,2,1,0,1,2,1)),('visual',(0,2,1,0,1,0,2,1))])
def test_notes_define_the_palette_and_steps_define_the_length(pattern,expected):
    c=instrument_sound();c.update(arp_notes=3,arp_steps=8,arp_pattern=pattern)
    assert phrase_pattern(c,0)==expected
    s=signals(3.);s['opening'][12]=1
    notes=gesture_notes(s,c)
    assert len(notes)==8 and len({n['semitones'] for n in notes})==3
    assert [n['time'] for n in notes]==sorted(n['time'] for n in notes)
    assert gesture_notes(s,c)==notes
    c['arp_notes']=1
    assert len({n['semitones'] for n in gesture_notes(s,c)})==1


def test_long_phrases_finish_before_retriggering_and_held_visuals_remain_quiet():
    c=instrument_sound();c.update(arp_steps=16,arp_rate=.5)
    s=signals(14.);assert not gesture_notes(s,c)
    s['opening'][12::60]=1
    notes=gesture_notes(s,c)
    assert len(notes)>=32
    for i in range(16,len(notes),16):
        assert notes[i]['time']>notes[i-1]['time']
        assert notes[i]['time']-notes[i-16]['time']>=16*.38
    s['presence'][:]=0
    assert not gesture_notes(s,c)


@pytest.mark.parametrize('key,value', [('arp_pitch',True),('arp_pitch',float('nan')),('arp_pitch',441),
    ('arp_notes',0),('arp_notes',9),('arp_notes',2.5),('arp_steps',True),('arp_steps',-1),
    ('arp_steps',17),('arp_pattern','invalid')])
def test_invalid_arpeggio_controls_fail(key,value):
    c=instrument_sound();c[key]=value
    with pytest.raises(ValueError): normalize_sound(c)


def test_long_pattern_is_identical_live_and_export_and_changes_are_soft():
    c=instrument_sound();c.update(arp_pitch=220.,arp_steps=16,arp_notes=6,arp_pattern='up_down',arp_rate=2.)
    s=signals(2.);s['opening'][12]=1;seq=dict(duration=2.,seed=31)
    live=LiveInstrument(seq,s,c)
    audio=np.concatenate([live.render() for _ in range(200)])
    assert np.array_equal(audio,render(c,s)) and np.isfinite(audio).all()
    changed=copy.deepcopy(c);changed.update(arp_pitch=330.,arp_steps=3,arp_pattern='down')
    live=LiveInstrument(seq,s,c);first=live.render(48000)
    live.update(changed);next_block=live.render()
    assert np.array_equal(next_block[0],audio[48000])
    assert abs(next_block[0]-first[-1]).max()<.1
    for _ in range(8): live.render()
    assert live.voice.config==changed


def test_dialog_controls_roundtrip_and_do_not_move_the_other_pitch(app):
    d=VisualSoundDialog();c=instrument_sound();c['pitch']=220.
    for key in NEW_FIELDS: c.pop(key)
    d.set_config(c);assert d.arp_pitch.value()==220.
    drafts=QSignalSpy(d.draftChanged);applied=QSignalSpy(d.configEdited)
    d.pitch.setValue(110.);assert d.arp_pitch.value()==220.
    d.arp_pitch.setValue(330.);assert d.pitch.value()==110.
    d.arp_notes.setValue(5);d.arp_steps.setValue(8);d.arp_pattern.setCurrentIndex(d.arp_pattern.findData('down'))
    wait_until(lambda:drafts.count()>0)
    assert applied.count()==0
    out=d.read_config();assert out['arp_notes']==5 and out['arp_steps']==8 and out['arp_pattern']=='down'
    d.apply();assert applied.at(0)[0]==out
    d.set_config(out);assert d.read_config()==out
    d.close()


def test_controls_save_and_undo(studio,tmp_path):
    from synth_composition import save_composition,load_composition
    original=copy.deepcopy(studio.composition)
    c=instrument_sound();c.update(arp_pitch=220.,arp_steps=12,arp_notes=5,arp_pattern='up_down')
    studio.apply_visual_sound(c)
    save_composition(tmp_path/'arp.json',studio.composition)
    assert load_composition(tmp_path/'arp.json')['generated_sound']==c
    studio.undo_composition();assert studio.composition==original
    studio.redo_composition();assert studio.sequence['generated_sound']==c
