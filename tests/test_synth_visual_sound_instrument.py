import copy
import numpy as np
import pytest
from media import Cancellation
from synth_visual_sound import RATE,instrument_sound,normalize_sound,pcm_blocks
from synth_visual_sound_instrument import note_envelope,oscillator_bank,instrument_blocks,instrument_controls


def signals(duration=2.):
    t=np.arange(round(duration*120)+1)/120
    return dict(time=t,presence=np.ones_like(t),expansion=np.full_like(t,.5),motion=np.zeros_like(t),opening=np.zeros_like(t))


def test_note_edges_and_filter_accents_are_soft():
    c=instrument_sound();dt=1/RATE
    env=note_envelope(np.array([-dt,0,dt,.32-dt,.32,.32+dt]),.32,c['attack'],c['release'])
    assert env[0]==env[1]==env[4]==env[5]==0
    assert env[2]<.000003 and env[3]<.000001
    s=signals();s['opening'][120]=1
    notes,accent=instrument_controls(s,c)
    raw=np.zeros_like(s['time'])
    for note in notes:
        raw=np.maximum(raw,note_envelope(s['time']-note['time'],max(note['duration'],c['attack']+c['release']),c['attack'],c['release']))
    assert accent[120]==0
    assert np.max(np.abs(np.diff(accent)))<np.max(np.abs(np.diff(raw)))*.6


@pytest.mark.parametrize('continuity', [0., 1.])
def test_pcm_has_no_block_seams_even_when_a_note_crosses_a_boundary(monkeypatch, continuity):
    import synth_visual_sound_instrument as instrument
    monkeypatch.setattr(instrument,'gesture_notes',lambda *_:[dict(time=.97,semitones=19,duration=.32,velocity=.8,pan=.2)])
    c=instrument_sound();c['continuity']=continuity;s=signals();s['presence']=np.linspace(.02, 1., len(s['time']));seq=dict(duration=2.,seed=56)
    regular=np.concatenate(list(instrument_blocks(seq,c,s,Cancellation())))
    irregular=np.concatenate(list(instrument_blocks(seq,c,s,Cancellation(),block_size=3571)))
    assert np.array_equal(regular,irregular)
    assert abs(regular[0]).max()==0 and abs(regular[-1]).max()<1e-7


def test_oscillator_switches_unison_detune_density_and_stereo_change_sound():
    c=instrument_sound();t=np.arange(RATE)/RATE
    baseline=oscillator_bank(t,150,c,1)
    for field,value in [('detune',0.),('unison',1),('density',0.),('width',0.)]:
        altered=copy.deepcopy(c);altered[field]=value
        assert not np.array_equal(baseline,oscillator_bank(t,150,altered,1))
    c['width']=0.;mono=oscillator_bank(t,150,c,1)
    assert np.array_equal(mono[:,0],mono[:,1])
    c['oscillators'][1]['enabled']=False
    assert not np.array_equal(mono,oscillator_bank(t,150,c,1))
    for osc in c['oscillators']: osc['enabled']=False
    s=signals();s['opening'][50]=1
    assert not np.concatenate(list(pcm_blocks(dict(duration=2.,generated_sound=c),signals=s))).any()


def test_manual_opening_works_with_motion_disabled():
    c=instrument_sound();s=signals();c['connections']['filter']['enabled']=False;c['connections']['arpeggio']['enabled']=False
    def render(): return np.concatenate(list(pcm_blocks(dict(duration=2.,generated_sound=c),signals=s)))
    first=render();s['motion'][:]=1
    assert np.array_equal(first,render())
    c['opening']=1
    assert not np.array_equal(first,render())


@pytest.mark.parametrize('key,value',[('unison',True),('unison',6),('opening',-1),('detune',36),('density',float('nan')),('attack',0),('release',.001),('continuity',True),('continuity',1.01),('continuity',float('nan'))])
def test_invalid_instrument_values_fail(key,value):
    c=instrument_sound();c[key]=value
    with pytest.raises(ValueError): normalize_sound(c)


def test_oscillator_data_is_validated_and_extreme_sound_is_bounded():
    c=instrument_sound();c['oscillators'][0]['transpose']=True
    with pytest.raises(ValueError): normalize_sound(c)
    c=instrument_sound();c.update(gain=1.,drive=1.,density=1.,unison=5,detune=35.,resonance=1.,opening=1.)
    for osc in c['oscillators']: osc.update(level=1.,wave='saw',transpose=24)
    for link in c['connections'].values(): link['amount']=2.
    s=signals(.7);s['opening'][10]=1
    audio=np.concatenate(list(pcm_blocks(dict(duration=.7,generated_sound=c),signals=s)))
    assert np.isfinite(audio).all() and abs(audio).max()<.721


def test_continuity_compresses_small_forms_but_preserves_silence_and_legacy_pcm():
    c=instrument_sound();s=signals(1.)
    c['connections']['filter']['enabled']=False;c['connections']['arpeggio']['enabled']=False
    def render(config):
        return np.concatenate(list(pcm_blocks(dict(duration=1.,generated_sound=config),signals=s)))
    full=render(c);s['presence'][:]=1/16
    linear=render(c)
    legacy=copy.deepcopy(c);legacy.pop('continuity')
    assert normalize_sound(legacy)['continuity']==0
    assert np.array_equal(render(legacy),linear)
    c['continuity']=1.;sustained=render(c)
    level=lambda a: np.sqrt(np.mean(a[RATE//4:3*RATE//4]**2))
    assert level(sustained)>level(linear)*10
    assert .7<level(sustained)/level(full)<.85
    s['presence'][:]=0
    assert not render(c).any()  # No unrelated audio floor when nothing is visible.
