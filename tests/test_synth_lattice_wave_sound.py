import copy
import numpy as np
import pytest

from synth_lattice_sound import color_wave_sound,ColorWaveVoice
from synth_lattice_wave_sound import WaveSine,wave_defaults,wave_position
from synth_visual_sound import normalize_sound,visual_signals,RATE
from synth_visual_sound_live import LiveInstrument
from synth_sequence import resolve_sequence_frame
from test_synth_lattice_sound import rhythmic_study
from test_synth_visual_sound_ui import app


def wave_config():
    c=normalize_sound(color_wave_sound());c['wave']['enabled']=True
    c['mixer']['wave']['solo']=True;c['wave']['reverb']=0.;c['space']['chorus']=0.
    return c


def test_radius_tracks_render_geometry_and_reverses_with_source_clock():
    seq=rhythmic_study();base=resolve_sequence_frame(seq,0)[-1]
    p=next(m['params'] for m in base['modules'] if m['id']=='chromatic_lattice')
    times=np.arange(0,5,.05)
    forward=np.array([wave_position(p,t,base) for t in times])
    reverse=np.array([wave_position(dict(p,direction=1),-t,base) for t in times])
    assert np.allclose(forward,reverse)
    faster=np.array([wave_position(dict(p,bpm=p['bpm']*2),t/2,base) for t in times])
    assert np.allclose(forward,faster)
    assert np.ptp(forward)>.1 and np.max(abs(np.diff(forward)))<.04
    signals=visual_signals(seq)
    assert np.allclose(np.interp(times,signals['time'],signals['lattice_radius']),forward)
    static=dict(p,pulse=0.)
    assert all(wave_position(static,t,base)==.5 for t in times)


def test_continuous_pitch_follows_outward_and_inward_motion_and_closes_phase():
    times=np.arange(2401)/120
    radius=.5+.1*np.sin(2*np.pi*times/5)
    signals=dict(time=times,presence=np.ones_like(times),lattice_radius=radius)
    settings=dict(wave_defaults(),low_pitch=110.,high_pitch=220.,glide=.02)
    wave=WaveSine(signals,settings,20.,True)
    assert wave.frequency[150]>wave.frequency[450]*1.9
    assert wave.frequency[-1]==wave.frequency[0]
    assert wave.phase[-1]==pytest.approx(round(wave.phase[-1]),abs=1e-8)
    pcm=wave.render(np.arange(20*RATE)/RATE)
    pieces=np.concatenate([wave.render(np.arange(i,min(i+613,20*RATE))/RATE) for i in range(0,20*RATE,613)])
    assert np.array_equal(pcm,pieces)
    assert np.max(abs(pcm[0]-pcm[-1]))<.006
    assert np.isfinite(pcm).all()
    signals['presence'][:]=0
    assert not np.any(WaveSine(signals,settings,20.,True).render(times))


def test_static_sine_is_pure_and_has_no_pitch_steps():
    times=np.arange(601)/120
    settings=dict(wave_defaults(),low_pitch=220.,high_pitch=220.)
    wave=WaveSine(dict(time=times,presence=np.ones_like(times),lattice_radius=times*0+.5),settings,5.,True)
    audio=wave.render(np.arange(RATE)/RATE)[:,0]
    spectrum=abs(np.fft.rfft(audio));peak=np.argmax(spectrum)
    assert peak==220
    assert spectrum[peak]/spectrum.sum()>.99999


def test_old_documents_stay_disabled_and_new_voice_matches_live():
    old=color_wave_sound();old.pop('wave');old['mixer'].pop('wave')
    loaded=normalize_sound(old)
    assert not loaded['wave']['enabled'] and loaded['mixer']['wave']['level_db']==-30
    seq=rhythmic_study();signals=visual_signals(seq);c=wave_config()
    offline=ColorWaveVoice(seq,c,signals).render(0,RATE)
    live=LiveInstrument(seq,signals,c)
    assert np.array_equal(offline,np.concatenate([live.render(480) for _ in range(100)]))
    assert .001<np.sqrt(np.mean(offline**2))<.004
    muted=copy.deepcopy(c);muted['mixer']['wave']['mute']=True
    assert not np.any(ColorWaveVoice(seq,muted,signals).render(0,RATE))
    changed=copy.deepcopy(c);changed['wave']['high_pitch']*=2
    live.update(changed)
    edited=np.concatenate([live.render(480) for _ in range(8)])
    assert np.max(abs(np.diff(edited,axis=0)))<.001
    assert live.position==RATE+8*480


@pytest.mark.parametrize('field,value',[('enabled',1),('low_pitch',float('nan')),('high_pitch',20),('glide',0),('reverb',2),('high_pitch_mode','bad')])
def test_wave_settings_validation(field,value):
    c=color_wave_sound();c['wave'][field]=value
    with pytest.raises(ValueError):normalize_sound(c)


def test_wave_controls_preserve_notes_and_pad_and_support_undo(app):
    from synth_visual_sound_ui import VisualSoundDialog
    c=normalize_sound(color_wave_sound());d=VisualSoundDialog();d.set_config(c)
    assert d.read_config()==c
    d.wave_sine.enabled.setChecked(True)
    changed=d.read_config()
    assert changed['wave']['enabled'] and changed['voices']==c['voices'] and changed['pad']==c['pad']
    d.undo_draft();assert d.read_config()==c
    d.redo_draft();assert d.read_config()['wave']['enabled']
    d.wave_sine.glide.setValue(120)
    assert d.read_config()['wave']['glide']==.12
    d.mixer.channels['wave']['level_db'].setValue(-36)
    assert d.read_config()['mixer']['wave']['level_db']==-36
    d.close()
