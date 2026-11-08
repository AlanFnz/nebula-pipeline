import copy
import numpy as np
import pytest

from synth_lattice_sound import ColorWaveVoice,color_notes,color_wave_sound
from synth_sound_mixer import MixerChannel,highpass_coefficients
from synth_visual_sound import normalize_sound,visual_signals,RATE
from synth_visual_sound_live import LiveInstrument
from synth_composition import save_composition,load_composition
from synth_lattice_recipes import lattice_composition
from test_synth_lattice_sound import rhythmic_study
from test_synth_visual_sound_ui import app


def config():
    c=normalize_sound(color_wave_sound());c['chime_layer'].update(enabled=True,reverb=0.,delay=0.)
    c['space']['chorus']=0.
    c['mixer']['chimes'].update(highpass_enabled=True,highpass_hz=320.,level_db=-8.)
    return c


def test_old_documents_are_opt_in_and_keep_exact_pcm():
    old=normalize_sound(color_wave_sound());old.pop('chime_layer');old['mixer'].pop('chimes')
    loaded=normalize_sound(old)
    assert not loaded['chime_layer']['enabled']
    seq=rhythmic_study();sig=visual_signals(seq)
    for engine in ('partials','analog','chimes'):
        for v in old['voices'].values():v['engine']=engine
        loaded=normalize_sound(old)
        assert np.array_equal(ColorWaveVoice(seq,old,sig).render(0,RATE),ColorWaveVoice(seq,loaded,sig).render(0,RATE))


def test_layer_is_additive_and_independent_of_opening_connection_and_tuning():
    seq=rhythmic_study();sig=visual_signals(seq);c=config()
    original=copy.deepcopy(c);original['chime_layer']['enabled']=False
    original_notes=color_notes(sig,original);combined=color_notes(sig,c)
    assert [n for n in combined if n['voice']!='chimes']==original_notes
    assert [n['time'] for n in combined if n['voice']=='chimes']==[n['time'] for n in original_notes if n['voice']=='strum']
    baseline=ColorWaveVoice(seq,original,sig).render(0,RATE)
    c['mixer']['chimes']['mute']=True
    assert np.array_equal(ColorWaveVoice(seq,c,sig).render(0,RATE),baseline)
    c['mixer']['chimes'].update(mute=False,solo=True)
    alone=ColorWaveVoice(seq,c,sig).render(0,RATE)
    c['connections']['strum']['enabled']=False
    c['voices']['strum']['pitch']*=2
    assert alone.any() and np.array_equal(ColorWaveVoice(seq,c,sig).render(0,RATE),alone)
    c['mixer']['chimes']['level_db']-=12
    quiet=ColorWaveVoice(seq,c,sig).render(0,RATE)
    assert np.sqrt(np.mean(quiet**2))<np.sqrt(np.mean(alone**2))*.27
    c['mixer']['chimes']['mute']=True
    assert not ColorWaveVoice(seq,c,sig).render(0,RATE).any()


def test_highpass_response_bypass_extremes_and_packet_continuity():
    m=config()['mixer']['chimes'];m.update(level_db=0.,highpass_hz=1000.,eq_enabled=False)
    t=np.arange(RATE)/RATE
    for frequency,expected in ((100,-40.),(1000,-3.01),(10000,0.)):
        x=np.repeat(np.sin(2*np.pi*frequency*t)[:,None],2,axis=1)
        y=MixerChannel(m).process(x)
        db=20*np.log10(np.linalg.norm(y[RATE//2:])/np.linalg.norm(x[RATE//2:]))
        assert db==pytest.approx(expected,abs=.1)
        chunked=MixerChannel(m)
        assert np.array_equal(y,np.concatenate([chunked.process(x[i:i+613]) for i in range(0,RATE,613)]))
    m['highpass_enabled']=False
    assert MixerChannel(m).process(x) is x
    for cutoff in (20,18000):
        *_,a1,a2=highpass_coefficients(cutoff)
        assert max(abs(np.roots([1,a1,a2])))<1


@pytest.mark.parametrize('target,field,value',[
    ('chime_layer','enabled',1),('chime_layer','pitch',0),('chime_layer','polyphony',1.5),
    ('chime_layer','scale','bad'),('chime_layer','decay',float('nan')),
    ('mixer','highpass_hz',19000),('mixer','highpass_hz',True),('mixer','highpass_enabled',1)])
def test_invalid_layer_controls_fail(target,field,value):
    c=config();(c['chime_layer'] if target=='chime_layer' else c['mixer']['chimes'])[field]=value
    with pytest.raises(ValueError):normalize_sound(c)


def test_live_export_loop_and_filter_edits_share_continuous_audio():
    seq=rhythmic_study();sig=visual_signals(seq);c=config()
    c['chime_layer'].update(reverb=.35,delay=.08)
    voice=ColorWaveVoice(seq,c,sig);length=round(seq['duration']*RATE)
    pcm=voice.render(0,length)
    live=LiveInstrument(seq,sig,c)
    played=np.concatenate([live.render(min(480,length-i)) for i in range(0,length,480)])
    assert np.array_equal(pcm,played)
    again=voice.render(length,length)
    assert np.max(abs(again-pcm))<1e-5
    assert abs(pcm[0]-pcm[-1]).max()<.05
    before=live.position;pieces=[]
    for cutoff in (20.,150.,1000.,18000.,400.):
        changed=copy.deepcopy(c);changed['mixer']['chimes']['highpass_hz']=cutoff
        live.update(changed);pieces.extend(live.render(480) for _ in range(5))
    y=np.concatenate(pieces)
    assert live.position==before+len(y) and np.isfinite(y).all()
    assert max(abs(np.diff(y,axis=0)).flat)<.08


def test_shared_oscillators_keep_both_crossfade_mixes_exact():
    seq=rhythmic_study();sig=visual_signals(seq);a=config()
    a['voices']['strum']['engine']='analog'
    b=copy.deepcopy(a);b['mixer']['chimes'].update(highpass_hz=2000.,level_db=-15.)
    expected=[ColorWaveVoice(seq,c,sig,warm_loop=False).render(24000,480) for c in (a,b)]
    shared={}
    actual=[ColorWaveVoice(seq,c,sig,warm_loop=False).render(24000,480,tone_cache=shared) for c in (a,b)]
    assert all(np.array_equal(x,y) for x,y in zip(actual,expected))


def test_layer_ui_history_and_saved_file_preserve_original_parts(app,tmp_path):
    from synth_visual_sound_ui import VisualSoundDialog
    c=normalize_sound(config());d=VisualSoundDialog();d.set_config(c)
    assert d.read_config()==c and d.tabs.isTabVisible(d.chimes_tab)
    states=[c]
    for control,value in ((d.chime_layer.knobs['decay'],1200.),(d.chime_layer.pitch,164.81377845643496),
                          (d.mixer.channels['chimes']['highpass_hz'],550.),(d.mixer.channels['chimes']['level_db'],-15.)):
        if control is d.chime_layer.pitch:control.number.setValue(value)
        else:control.setValue(value)
        states.append(d.read_config())
    for field in ('voices','connections','pad','wave','space','delay'):assert states[-1][field]==c[field]
    for key in ('body','arpeggio','pad','wave'):assert states[-1]['mixer'][key]==c['mixer'][key]
    for expected in reversed(states[:-1]):assert d.undo_draft() and d.read_config()==expected
    for expected in states[1:]:assert d.redo_draft() and d.read_config()==expected
    doc=lattice_composition();doc['generated_sound']=d.read_config();save_composition(tmp_path/'layer.json',doc)
    assert load_composition(tmp_path/'layer.json')['generated_sound']==states[-1]
    d.close()
