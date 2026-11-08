import copy
import numpy as np
import pytest

from synth_sound_sub import SubVoice,sub_defaults,sub_frequency
from synth_lattice_sound import ColorWaveVoice,color_wave_sound,color_notes
from synth_visual_sound import normalize_sound,visual_signals,RATE
from synth_visual_sound_live import LiveInstrument
from synth_composition import save_composition,load_composition
from synth_lattice_recipes import lattice_composition
from test_synth_lattice_sound import rhythmic_study
from test_synth_visual_sound_ui import app


def config():
    c=normalize_sound(color_wave_sound());c['sub'].update(enabled=True,octaves_below=3)
    c['pad'].update(pitch=82.4068892282175,follow_root=False,octave=2)
    return c


def test_old_documents_and_mute_preserve_existing_pcm():
    old=normalize_sound(color_wave_sound());old.pop('sub');old['mixer'].pop('sub')
    loaded=normalize_sound(old)
    assert not loaded['sub']['enabled']
    seq=rhythmic_study();sig=visual_signals(seq)
    baseline=ColorWaveVoice(seq,old,sig).render(0,RATE)
    assert np.array_equal(baseline,ColorWaveVoice(seq,loaded,sig).render(0,RATE))
    loaded['sub']['enabled']=True;loaded['mixer']['sub']['mute']=True
    assert np.array_equal(baseline,ColorWaveVoice(seq,loaded,sig).render(0,RATE))
    assert color_notes(sig,loaded)==color_notes(sig,old)


def test_pitch_harmonics_filter_and_mono_loop():
    s=dict(sub_defaults(),octaves_below=3,body=0,cutoff=800)
    assert sub_frequency(82.4068892282175,2,s)==pytest.approx(41.20344461410875)
    t=np.arange(RATE*5)/RATE
    voice=SubVoice(82.4068892282175,2,s,5.)
    x=voice.render(t);spec=abs(np.fft.rfft(x[:,0]))
    assert np.argmax(spec)/5==41.2
    assert np.array_equal(x[:,0],x[:,1])
    assert abs(np.mean(x))<1e-10
    assert np.allclose(x,voice.render(t+5.),atol=1e-10)
    assert np.array_equal(x,np.concatenate([voice.render(t[i:i+613]) for i in range(0,len(t),613)]))
    s['body']=1.
    bright=SubVoice(82.4068892282175,2,s,5.).render(t)
    b=abs(np.fft.rfft(bright[:,0]));fund=np.argmax(b)
    assert b[fund*2]/b[fund]==pytest.approx(.18,abs=.001)
    s['cutoff']=40.
    dark=SubVoice(82.4068892282175,2,s,5.).render(t)
    d=abs(np.fft.rfft(dark[:,0]));assert d[fund*2]/d[fund]<.07


def test_sub_is_dry_and_independent_of_pad_enable_and_harmony():
    seq=rhythmic_study();sig=visual_signals(seq);c=config()
    c['mixer']['sub']['solo']=True
    dry=ColorWaveVoice(seq,c,sig).render(0,RATE)
    c['space'].update(chorus=1.,decay=6.);c['pad'].update(enabled=True,harmony='major9',detune=20.,reverb=1.)
    c['choir'].update(enabled=True,reverb=1.)
    assert np.array_equal(dry,ColorWaveVoice(seq,c,sig).render(0,RATE))
    assert np.array_equal(dry[:,0],dry[:,1])
    c['mixer']['sub']['level_db']-=6.
    quiet=ColorWaveVoice(seq,c,sig).render(0,RATE)
    assert np.linalg.norm(quiet)/np.linalg.norm(dry)==pytest.approx(10**(-6/20),abs=.001)
    c['mixer']['sub']['mute']=True
    assert not ColorWaveVoice(seq,c,sig).render(0,RATE).any()


@pytest.mark.parametrize('field,value',[('enabled',1),('octaves_below',0),('octaves_below',1.5),
    ('body',float('nan')),('body',True),('cutoff',900)])
def test_invalid_settings_fail(field,value):
    c=config();c['sub'][field]=value
    with pytest.raises(ValueError):normalize_sound(c)


def test_live_export_and_changes_remain_continuous():
    seq=rhythmic_study();sig=visual_signals(seq);c=config();c['mixer']['sub'].update(solo=True,low_db=3.)
    voice=ColorWaveVoice(seq,c,sig);n=round(seq['duration']*RATE)
    x=voice.render(0,n);live=LiveInstrument(seq,sig,c);live.start_fade=1920
    y=np.concatenate([live.render(min(480,n-i)) for i in range(0,n,480)])
    assert np.array_equal(x,y)
    assert np.max(abs(x[0]-x[-1]))<.002
    chunks=[]
    for field,value in (('octaves_below',2),('cutoff',40.),('body',1.)):
        draft=copy.deepcopy(c);draft['sub'][field]=value;live.update(draft)
        chunks.extend(live.render() for _ in range(8))
    y=np.concatenate(chunks)
    assert np.isfinite(y).all() and np.max(abs(np.diff(y,axis=0)))<.01
    c['seamless_loop']=False
    edge=ColorWaveVoice(seq,c,sig,warm_loop=False)
    assert not edge.render(0,1).any()
    assert np.max(abs(edge.render(n-1,1)))<1e-6


def test_controls_pitch_readout_undo_and_saved_roundtrip(app,tmp_path):
    from synth_visual_sound_ui import VisualSoundDialog
    c=config();d=VisualSoundDialog();d.set_config(c)
    assert d.read_config()==c and d.tabs.isTabVisible(d.sub_tab)
    assert 'E1' in d.sub.pitch_label.text() and '41.20 Hz' in d.sub.pitch_label.text()
    states=[c]
    for knob,value in ((d.sub.knobs['octaves_below'],2),(d.sub.knobs['body'],30.),
                       (d.mixer.channels['sub']['level_db'],-14.)):
        knob.setValue(value);states.append(d.read_config())
    assert '82.41 Hz' in d.sub.pitch_label.text()
    for key in c:
        if key not in ('sub','mixer'):assert states[-1][key]==c[key]
    for key in c['mixer']:
        if key!='sub':assert states[-1]['mixer'][key]==c['mixer'][key]
    for expected in reversed(states[:-1]):assert d.undo_draft() and d.read_config()==expected
    for expected in states[1:]:assert d.redo_draft() and d.read_config()==expected
    doc=lattice_composition();doc['generated_sound']=d.read_config();save_composition(tmp_path/'sub.json',doc)
    assert load_composition(tmp_path/'sub.json')['generated_sound']==states[-1]
    d.pad_space.follow.setChecked(True)
    d.color_wave.voices['strum']['pitch'].setValue(110.)
    assert '110.00 Hz' in d.sub.pitch_label.text()
    d.close()
