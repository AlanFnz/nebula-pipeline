import copy
import numpy as np
import pytest

from synth_sound_choir import ChoirVoice,choir_defaults,vowel_tables
from synth_sound_analog import pad_defaults
from synth_lattice_sound import ColorWaveVoice,color_wave_sound,color_notes
from synth_visual_sound import normalize_sound,visual_signals,RATE
from synth_visual_sound_live import LiveInstrument
from synth_composition import save_composition,load_composition
from synth_lattice_recipes import lattice_composition
from test_synth_lattice_sound import rhythmic_study
from test_synth_visual_sound_ui import app


def config():
    c=normalize_sound(color_wave_sound())
    c['choir'].update(enabled=True,reverb=0.)
    c['pad']['harmony']='minor9'
    return c


def test_old_documents_and_disabled_layer_keep_exact_audio():
    old=normalize_sound(color_wave_sound());old.pop('choir');old['mixer'].pop('choir')
    loaded=normalize_sound(old)
    assert not loaded['choir']['enabled']
    seq=rhythmic_study();sig=visual_signals(seq)
    assert np.array_equal(ColorWaveVoice(seq,old,sig).render(0,RATE),ColorWaveVoice(seq,loaded,sig).render(0,RATE))
    changed=copy.deepcopy(loaded);changed['choir'].update(vowel=0.,cutoff=9000.,air=1.)
    assert np.array_equal(ColorWaveVoice(seq,loaded,sig).render(0,RATE),ColorWaveVoice(seq,changed,sig).render(0,RATE))


def test_pitched_formants_and_bandlimit():
    hz=200.;oo,ah=vowel_tables(hz,4200.)
    a=abs(np.fft.rfft(oo[:-1]));b=abs(np.fft.rfft(ah[:-1]))
    assert a[1]>.1 and b[1]>.1
    assert a[2]/a[4]>b[2]/b[4]  # OO has a lower first formant than AH.
    assert np.max(a[int(RATE*.4/hz)+1:])<1e-10
    pad=dict(pad_defaults(),octave=0,harmony='minor9')
    choir=ChoirVoice(hz,pad,dict(choir_defaults(),detune=0,air=0,motion=0),20.)
    frequencies=[part[0] for part in choir.parts][::3]
    expected=hz*2**(np.array([0,7,15,22,26])/12)
    assert np.max(abs(1200*np.log2(frequencies/expected)))<.3
    up=ChoirVoice(hz,pad,dict(choir_defaults(),octave=1,detune=0),20.)
    assert np.allclose([p[0] for p in up.parts],np.repeat(expected*2,3),atol=.025)


def test_sustained_ensemble_wraps_with_all_controls_and_packet_sizes():
    p=dict(pad_defaults(),harmony='minor9')
    s=dict(choir_defaults(),air=.7,motion=.8,detune=9.)
    voice=ChoirVoice(82.4069,p,s,5.)
    t=np.arange(5000)/RATE
    x=voice.render(t);wrapped=voice.render(t+5.)
    assert np.allclose(x,wrapped,atol=1e-9)
    chunked=np.concatenate([voice.render(t[i:i+479]) for i in range(0,len(t),479)])
    assert np.array_equal(x,chunked)
    assert np.linalg.norm(x[:,0]-x[:,1])>np.linalg.norm(x)*.2
    edge=voice.render(np.array([5.-1/RATE,0.]))
    assert np.max(abs(edge[1]-edge[0]))<.1


def test_mixer_independent_layer_follows_pad_even_when_pad_is_off():
    seq=rhythmic_study();sig=visual_signals(seq);c=config()
    notes=color_notes(sig,c);c['mixer']['choir']['solo']=True
    a=ColorWaveVoice(seq,c,sig).render(0,RATE)
    assert a.any()
    c['voices']['steps']['pitch']*=2
    assert np.array_equal(a,ColorWaveVoice(seq,c,sig).render(0,RATE))
    c['pad']['pitch']*=2;c['pad']['follow_root']=False
    assert not np.array_equal(a,ColorWaveVoice(seq,c,sig).render(0,RATE))
    c['mixer']['choir']['mute']=True
    assert not ColorWaveVoice(seq,c,sig).render(0,RATE).any()
    c['choir']['enabled']=False
    assert color_notes(sig,config())==notes


@pytest.mark.parametrize('field,value',[('enabled',1),('octave',.5),('octave',2),('vowel',1.2),
    ('cutoff',float('nan')),('air',True),('detune',13),('motion',-1)])
def test_invalid_settings_are_rejected(field,value):
    c=config();c['choir'][field]=value
    with pytest.raises(ValueError):normalize_sound(c)


def test_live_export_loop_and_edit_crossfades():
    seq=rhythmic_study();sig=visual_signals(seq);c=config()
    c['choir']['reverb']=.9;c['space'].update(chorus=.3,decay=1.2)
    voice=ColorWaveVoice(seq,c,sig);n=round(seq['duration']*RATE)
    rendered=voice.render(0,n);live=LiveInstrument(seq,sig,c)
    live.start_fade=1920  # compare steady output, excluding monitor-only fade-in
    played=np.concatenate([live.render(min(480,n-i)) for i in range(0,n,480)])
    assert np.allclose(rendered,played,atol=1e-7)
    assert np.max(abs(rendered[-1]-rendered[0]))<.03
    chunks=[]
    for value in (0.,1.,.6):
        draft=copy.deepcopy(c);draft['choir']['vowel']=value;live.update(draft)
        chunks.extend(live.render() for _ in range(8))
    x=np.concatenate(chunks)
    assert np.isfinite(x).all() and np.max(abs(np.diff(x,axis=0)))<.08


def test_choir_ui_undo_and_save_preserve_rest_of_sound(app,tmp_path):
    from synth_visual_sound_ui import VisualSoundDialog
    c=config();d=VisualSoundDialog();d.set_config(c)
    assert d.read_config()==c and d.tabs.isTabVisible(d.choir_tab)
    states=[c]
    for knob,value in ((d.choir.knobs['vowel'],30.),(d.choir.knobs['cutoff'],3000.),
                       (d.mixer.channels['choir']['level_db'],-16.)):
        knob.setValue(value);states.append(d.read_config())
    d.choir.enabled.setChecked(False);states.append(d.read_config())
    for key in c:
        if key not in ('choir','mixer'):assert states[-1][key]==c[key]
    for key in c['mixer']:
        if key!='choir':assert states[-1]['mixer'][key]==c['mixer'][key]
    for expected in reversed(states[:-1]):assert d.undo_draft() and d.read_config()==expected
    for expected in states[1:]:assert d.redo_draft() and d.read_config()==expected
    doc=lattice_composition();doc['generated_sound']=d.read_config();save_composition(tmp_path/'choir.json',doc)
    assert load_composition(tmp_path/'choir.json')['generated_sound']==states[-1]
    d.close()
