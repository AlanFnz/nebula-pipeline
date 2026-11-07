"""Analog color voices: legacy compatibility, musical timing, tails and live edits."""
import copy
import numpy as np
import pytest
from media import Cancellation
from synth_composition import compile_composition
from synth_lattice_recipes import lattice_composition
from synth_lattice_sound import color_wave_sound,ColorWaveVoice,color_notes,color_blocks
from synth_sound_analog import StereoSpace,space_defaults,analog_note,root_pad,PAD_HARMONIES
from synth_visual_sound import normalize_sound,visual_signals,RATE
from synth_visual_sound_live import LiveInstrument
from test_synth_visual_sound_ui import app


def patch():
    c=color_wave_sound()
    for v in c['voices'].values():v.update(engine='analog',reverb=.25)
    c['pad']['enabled']=True;c['space']['chorus']=.45
    return normalize_sound(c)


def sequence(duration=5):
    p=lattice_composition();p['generated_sound']=patch();s=compile_composition(p)
    s['duration']=duration;s['cues']=[x for x in s['cues'] if x['time']<duration]
    for state in s['states'].values():state['overrides'].update({'chromatic_lattice.color_rhythm':1,'chromatic_lattice.minimum':.22})
    return s


def test_pre_analog_documents_keep_their_original_audio():
    old=color_wave_sound();old.pop('pad');old.pop('space');old['mixer'].pop('pad')
    for v in old['voices'].values():
        for key in ('engine','analog','reverb'):v.pop(key)
    loaded=normalize_sound(old)
    assert loaded==normalize_sound(color_wave_sound())
    assert not loaded['pad']['enabled'] and loaded['space']['chorus']==0


@pytest.mark.parametrize('path,value',[(('pad','enabled'),1),(('pad','octave'),.5),
    (('pad','pitch'),float('nan')),(('pad','harmony'),'invalid'),(('space','decay'),0),(('space','damping'),1.1),
    (('voices','strum','engine'),'unknown'),(('voices','steps','analog','unison'),2.5),
    (('voices','steps','analog','detune'),-1),(('voices','steps','analog','cutoff'),True)])
def test_invalid_controls_are_rejected(path,value):
    c=patch();target=c
    for key in path[:-1]:target=target[key]
    target[path[-1]]=value
    with pytest.raises(ValueError):normalize_sound(c)


def test_synth_has_harmonics_a_stable_root_and_a_moving_filter():
    v=patch()['voices']['steps'];v['analog'].update(unison=1,sub=0.,detune=0.,cutoff=2500.,sweep=0.)
    age=np.arange(RATE)/RATE;y=analog_note(age,220.,v).mean(axis=1)
    spectrum=np.abs(np.fft.rfft(y*np.hanning(RATE)))
    assert np.argmax(spectrum)==220
    assert spectrum[440]>.08*spectrum[220]
    dull=analog_note(age,220.,dict(v,analog=dict(v['analog'],cutoff=150.)))
    assert np.sqrt(np.mean(dull*dull))<np.sqrt(np.mean(y*y))*.6
    rich=analog_note(age,220.,dict(v,analog=dict(v['analog'],unison=3,detune=7.)))
    assert np.sqrt(np.mean((rich[:,0]-rich[:,1])**2))>.005


def test_reverb_diffuses_an_impulse_and_is_block_size_independent():
    x=np.zeros((RATE,2));x[0]=.5;settings=dict(space_defaults(),chorus=.5)
    full=StereoSpace(settings).process(x,x,0)
    fx=StereoSpace(settings);blocks=np.concatenate([fx.process(x[i:i+477],x[i:i+477],i) for i in range(0,len(x),477)])
    assert np.max(abs(full-blocks))<1e-12
    assert np.count_nonzero(full[RATE//4:])>RATE//2
    assert np.isfinite(full).all() and np.max(abs(full))<1
    clone=StereoSpace(dict(settings,decay=4.));clone.inherit(fx)
    assert np.array_equal(clone.combs[0].buffer,fx.combs[0].buffer)
    assert clone.combs[0].buffer is not fx.combs[0].buffer


def test_pad_is_tuned_to_root_octaves_and_closes_the_loop():
    p=patch()['pad'];t=np.arange(RATE)/RATE
    p.update(detune=0.,motion=0.,octave=1)
    audio=root_pad(t,110.,p,5.).mean(axis=1)
    spec=np.abs(np.fft.rfft(audio*np.hanning(len(audio))))
    assert np.argmax(spec) in (110,220)
    a=root_pad(t,110.,p,5.);b=root_pad(t+5,110.,p,5.)
    assert np.max(abs(a-b))<1e-8


def test_old_pad_loads_as_root_and_open_chord_contains_its_notes():
    c=patch();c['pad'].pop('harmony')
    assert normalize_sound(c)['pad']['harmony']=='root'
    p=dict(c['pad'],harmony='minor9',octave=0,detune=0.,motion=0.,cutoff=2000.)
    t=np.arange(2*RATE)/RATE;y=root_pad(t,110.,p,20.).mean(axis=1)
    spectrum=np.abs(np.fft.rfft(y*np.hanning(len(y))))
    for semitones in (0,7,15,22,26):
        hz=round(110*2**(semitones/12)*20)/20;index=round(hz*2)
        assert np.max(spectrum[index-2:index+3])>.025*np.max(spectrum)
    assert np.isfinite(y).all() and np.max(abs(y))<1.5


@pytest.mark.parametrize('harmony',[key for key,_,_ in PAD_HARMONIES if key!='root'])
def test_open_chords_close_the_loop(harmony):
    p=dict(patch()['pad'],harmony=harmony)
    t=np.arange(480)/RATE
    assert np.max(abs(root_pad(t,82.4069,p,20.)-root_pad(t+20,82.4069,p,20.)))<1e-8


def test_new_timbre_keeps_visual_notes_and_matches_live_export():
    s=sequence();signals=visual_signals(s);c=s['generated_sound']
    assert color_notes(signals,c)==color_notes(signals,color_wave_sound())
    voice=ColorWaveVoice(s,c,signals)
    offline=np.concatenate([voice.render(i,480) for i in range(0,5*RATE,480)])
    live=LiveInstrument(s,signals,c)
    played=np.concatenate([live.render(480) for _ in range(500)])
    assert np.max(abs(played-offline))<1e-6
    repeated=voice.render(5*RATE,5*RATE)
    assert np.max(abs(repeated-offline))<2e-5
    jump=abs(offline[0]-offline[-1]).max()
    assert jump<np.quantile(abs(np.diff(offline,axis=0)),.999)
    assert .01<np.sqrt(np.mean(offline*offline))<.3 and np.max(abs(offline))<.9
    # The root pad fills the return, while the original attacks remain intact.
    assert np.sqrt(np.mean(offline[4*RATE:]**2))>.001


def test_pad_mute_solo_and_live_edits_preserve_room_history():
    s=sequence();sig=visual_signals(s);c=s['generated_sound']
    c['mixer']['pad']['solo']=True
    solo=ColorWaveVoice(s,c,sig,warm_loop=False).render(RATE,4800)
    assert solo.any()
    c['mixer']['pad']['mute']=True
    assert not ColorWaveVoice(s,c,sig,warm_loop=False).render(RATE,4800).any()
    c['mixer']['pad'].update(mute=False,solo=False)
    live=LiveInstrument(s,sig,c);live.render(4800)
    previous=copy.deepcopy(live.voice.space.combs[0].buffer)
    edited=copy.deepcopy(c);edited['voices']['steps']['analog']['cutoff']=2300;edited['space']['decay']=4.
    live.update(edited);samples=np.concatenate([live.render(480) for _ in range(10)])
    assert live.old is None and live.voice.config==edited and np.isfinite(samples).all()
    assert previous.any() and live.voice.space.combs[0].buffer.any()
    assert np.max(abs(np.diff(samples,axis=0)))<.1


def test_pad_analog_and_space_controls_round_trip_and_undo(app):
    from synth_visual_sound_ui import VisualSoundDialog
    d=VisualSoundDialog();c=patch();d.set_config(c)
    assert d.read_config()==c and d.tabs.isTabVisible(5)
    d.color_wave.voices['strum']['analog']['cutoff'].setValue(2400.)
    assert d.read_config()['voices']['strum']['analog']['cutoff']==2400.
    d.undo_draft();assert d.read_config()==c
    d.pad_space.space['decay'].setValue(4.1)
    assert d.read_config()['space']['decay']==4.1
    d.undo_draft();assert d.read_config()==c
    d.pad_space.enabled.setChecked(False);assert not d.read_config()['pad']['enabled']
    d.undo_draft();assert d.read_config()==c
    d.pad_space.harmony.setCurrentIndex(d.pad_space.harmony.findData('minor9'))
    assert d.read_config()['pad']['harmony']=='minor9'
    d.undo_draft();assert d.read_config()==c
    d.mixer.channels['pad']['level_db'].setValue(-26.)
    assert d.read_config()['mixer']['pad']['level_db']==-26.
    d.close()


def test_live_start_does_not_run_a_long_room_preroll(monkeypatch):
    from synth_lattice_sound import _ROOM_CACHE
    _ROOM_CACHE.clear();s=sequence();sig=visual_signals(s)
    def unexpected(*args,**kwargs):raise AssertionError('Live startup must not synthesize a room preroll')
    monkeypatch.setattr(ColorWaveVoice,'render',unexpected)
    live=LiveInstrument(s,sig,s['generated_sound'])
    assert live.voice.space is not None


def test_chord_pad_cache_preserves_audio_during_live_parameter_edits():
    s=sequence();c=s['generated_sound'];c['pad']['harmony']='minor9';sig=visual_signals(s)
    a=ColorWaveVoice(s,c,sig,warm_loop=False);b=ColorWaveVoice(s,c,sig,warm_loop=False)
    cache={};plain=a.render(RATE,480);shared=b.render(RATE,480,tone_cache=cache)
    assert np.array_equal(plain,shared)
    assert any(k[0]=='pad' for k in cache)
    live=LiveInstrument(s,sig,c);live.render(4800)
    change=copy.deepcopy(c);change['pad']['harmony']='sus2';live.update(change)
    audio=np.concatenate([live.render(480) for _ in range(10)])
    assert live.voice.config['pad']['harmony']=='sus2' and np.isfinite(audio).all()
    assert np.max(abs(np.diff(audio,axis=0)))<.1
