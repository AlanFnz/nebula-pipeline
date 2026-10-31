import copy

import numpy as np
import pytest

from synth_composition import compile_composition, load_composition, save_composition
from synth_pleated_recipes import pleated_acid_composition, pleated_composition
from synth_preview import _visual_document
from synth_visual_sound import RATE, acid_sound, normalize_sound, pcm_blocks
from synth_visual_sound_acid import gesture_notes, resonant_lowpass


def controls(duration=3.):
    t=np.arange(round(duration*120)+1)/120
    return dict(time=t,presence=np.ones_like(t),expansion=np.full_like(t,.5),
                motion=np.zeros_like(t),opening=np.zeros_like(t))


def test_held_geometry_does_not_run_a_free_arpeggiator():
    s=controls();config=acid_sound()
    assert gesture_notes(s,config)==[]
    s['motion'][:]=.3
    assert gesture_notes(s,config)==[]
    # Reopening is an actual visual event, including with no camera movement.
    s['opening'][120]=1
    notes=gesture_notes(s,config)
    assert len(notes)==4 and notes[0]['time']==1.
    assert notes[-1]['time']-notes[0]['time']<.7
    faster=copy.deepcopy(config);faster['arp_rate']=2.
    assert gesture_notes(s,faster)[-1]['time']<notes[-1]['time']
    s['presence'][:]=0
    assert gesture_notes(s,config)==[]


def test_gestures_trigger_notes_while_pitch_stays_on_a_musical_scale():
    s=controls(6.);t=s['time'];s['motion']=((t>.3)&(t<1.2)|((t>3)&(t<4))).astype(float)
    notes=gesture_notes(s,acid_sound())
    assert len(notes)==7 and notes[4]['time']>3
    assert all(n['semitones']%12 in (0,3,5,7,10) for n in notes)
    assert notes[4]['time']-notes[3]['time']>1.5


def test_filter_opens_and_resonance_emphasizes_its_cutoff():
    t=np.arange(RATE)/RATE
    source=.1*np.sin(2*np.pi*1000*t)
    def level(cutoff,resonance):
        out,_=resonant_lowpass(source,np.full_like(t,cutoff),resonance,(0.,0.))
        return np.sqrt(np.mean(out[RATE//2:]**2))
    assert level(4000,.1)>level(200,.1)*10
    assert level(1000,.9)>level(1000,0)*4


def test_no_noise_or_pitch_ramp_in_the_held_triangle():
    s=controls();config=acid_sound();config['pitch']=150.
    config['connections']['arpeggio']['enabled']=False
    seq=dict(duration=3.,generated_sound=config)
    audio=np.concatenate(list(pcm_blocks(seq,signals=s)))[:,0]
    # Exactly periodic after envelopes settle; there is no hiss or motor glide.
    tail=audio[RATE:2*RATE]
    assert np.max(np.abs(tail[320:]-tail[:-320]))<.0001
    peak=np.argmax(np.abs(np.fft.rfft(tail)))
    assert peak==150


@pytest.mark.parametrize('field,value',[('pitch',40),('resonance',1.1),('scale','random'),('arp_rate',0),('cutoff',float('inf')),('sweep',100)])
def test_invalid_acid_settings_fail(field,value):
    c=acid_sound();c[field]=value
    with pytest.raises(ValueError): normalize_sound(c)


def test_extreme_modulation_is_finite_bounded_and_cancellable():
    s=controls(1.);s['motion']=np.linspace(0,1,len(s['time']));s['opening'][10]=1
    config=acid_sound();config.update(resonance=1.,gain=1.,cutoff=80.,sweep=12000.,pitch=440.)
    for link in config['connections'].values(): link['amount']=2.
    audio=np.concatenate(list(pcm_blocks(dict(duration=1.,generated_sound=config),signals=s)))
    assert np.isfinite(audio).all() and abs(audio).max()<.73


def test_acid_study_roundtrips_without_changing_visual_document(tmp_path):
    project=pleated_acid_composition();save_composition(tmp_path/'acid.json',project)
    restored=load_composition(tmp_path/'acid.json')
    assert restored==project
    silent=compile_composition(pleated_composition());audible=compile_composition(restored)
    a=_visual_document(audible);b=_visual_document(silent)
    a['name']=b['name']
    assert a==b
