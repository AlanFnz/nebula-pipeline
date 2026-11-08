import copy

import numpy as np
import pytest

from synth_composition import load_composition,save_composition,compile_composition
from synth_lattice_recipes import lattice_composition
from synth_lattice_sound import ColorWaveVoice,color_notes,color_wave_sound
from synth_sound_chimes import chime_note
from synth_visual_sound import normalize_sound,visual_signals,RATE
from synth_visual_sound_live import LiveInstrument
from test_synth_visual_sound_ui import app


def patch():
    c=color_wave_sound()
    c['voices']['strum'].update(engine='chimes',pitch=329.6275569,decay=.7,polyphony=0,span=24)
    return normalize_sound(c)


def study():
    doc=lattice_composition();doc['generated_sound']=patch()
    seq=compile_composition(doc);seq['duration']=5
    seq['cues']=[x for x in seq['cues'] if x['time']<5]
    for state in seq['states'].values():
        state['overrides'].update({'chromatic_lattice.color_rhythm':1,'chromatic_lattice.minimum':.22})
    return seq


def test_old_engines_keep_exact_audio_without_chime_fields():
    seq=study();sig=visual_signals(seq)
    for engine in ('partials','analog'):
        old=normalize_sound(color_wave_sound())
        for voice in old['voices'].values():voice['engine']=engine;voice.pop('chimes')
        loaded=normalize_sound(old)
        a=ColorWaveVoice(seq,old,sig).render(0,RATE)
        b=ColorWaveVoice(seq,loaded,sig).render(0,RATE)
        assert np.array_equal(a,b)


@pytest.mark.parametrize('field,value',[('shimmer',float('nan')),('shimmer',1.1),('strike',0),('strike',True),('tuning','bad')])
def test_chime_controls_reject_invalid_values(field,value):
    c=patch();c['voices']['strum']['chimes'][field]=value
    with pytest.raises(ValueError):normalize_sound(c)


def test_tubes_have_metallic_modes_a_pitched_core_and_smooth_edges():
    v=patch()['voices']['strum'];v['chimes']['shimmer']=0.
    age=np.arange(-480,2*RATE)/RATE
    y=chime_note(age,440.,v)
    assert not y[:481].any() and np.isfinite(y).all()
    spec=np.abs(np.fft.rfft(y[480:]*np.hanning(2*RATE)))
    assert np.argmax(spec)==880
    for ratio in (2.76,5.40):
        peak=round(440*ratio*2)
        assert max(spec[peak-3:peak+4])>.02*max(spec)
    dark=chime_note(age,440.,dict(v,brightness=0.))
    assert np.sqrt(np.mean(dark**2))<np.sqrt(np.mean(y**2))
    tail=chime_note(np.array([6*v['decay']-1/RATE,6*v['decay'],6*v['decay']+1/RATE]),440.,v)
    assert abs(tail).max()<1e-7
    # No state reset at synthesis block boundaries or at a seek.
    parts=np.concatenate([chime_note(age[i:i+613],440.,v) for i in range(0,len(age),613)])
    assert np.array_equal(parts,y)


def test_cascade_timing_live_audio_and_loop_are_consistent():
    seq=study();c=seq['generated_sound'];sig=visual_signals(seq)
    original=copy.deepcopy(c);original['voices']['strum']['engine']='partials'
    assert color_notes(sig,c)==color_notes(sig,original)
    voice=ColorWaveVoice(seq,c,sig)
    offline=voice.render(0,5*RATE)
    live=LiveInstrument(seq,sig,c)
    played=np.concatenate([live.render(480) for _ in range(500)])
    assert np.array_equal(played,offline)
    assert np.array_equal(voice.render(5*RATE,5*RATE),offline)
    assert abs(offline[0]-offline[-1]).max()<np.quantile(abs(np.diff(offline,axis=0)),.999)
    assert .01<np.sqrt(np.mean(offline**2))<.4
    old_position=live.position
    edited=copy.deepcopy(c);edited['voices']['strum']['chimes']['shimmer']=.8
    live.update(edited);packet=live.render(480)
    assert live.position==old_position+480 and np.isfinite(packet).all()
    assert abs(np.diff(packet,axis=0)).max()<.2


def test_chimes_save_reopen_and_ui_history_preserve_other_voices(app,tmp_path):
    from synth_visual_sound_ui import VisualSoundDialog
    doc=lattice_composition();doc['generated_sound']=patch()
    save_composition(tmp_path/'chimes.json',doc)
    saved=load_composition(tmp_path/'chimes.json')
    assert saved['generated_sound']==doc['generated_sound']
    d=VisualSoundDialog();d.set_config(saved['generated_sound']);before=d.read_config()
    assert before==doc['generated_sound']
    control=d.color_wave.voices['strum']
    assert not control['chimes_box'].isHidden() and control['analog_box'].isHidden()
    assert control['character'].isHidden() and not control['brightness'].isHidden()
    control['chimes']['strike'].setValue(12.)
    changed=d.read_config();assert changed['voices']['strum']['chimes']['strike']==.012
    assert changed['voices']['steps']==before['voices']['steps']
    assert changed['pad']==before['pad'] and changed['wave']==before['wave']
    d.undo_draft();assert d.read_config()==before
    d.redo_draft();assert d.read_config()==changed
    d.close()


def test_harmonic_resonances_keep_the_note_clear_and_legacy_metal_is_unchanged():
    v=patch()['voices']['strum'];v['chimes']['shimmer']=0.
    age=np.arange(2*RATE)/RATE
    legacy=copy.deepcopy(v);legacy['chimes'].pop('tuning')
    old=chime_note(age,220.,legacy)
    assert np.array_equal(old,chime_note(age,220.,v))
    v['chimes']['tuning']='harmonic';tuned=chime_note(age,220.,v)
    spectrum=abs(np.fft.rfft(tuned*np.hanning(len(tuned))))
    original=abs(np.fft.rfft(old*np.hanning(len(old))))
    assert np.argmax(spectrum)==440  # 220 Hz, half-Hz bins.
    for ratio in (3,5,9):
        center=440*ratio
        assert max(spectrum[center-2:center+3])>.002*max(spectrum)
    for ratio in (2.76,5.4):
        center=round(440*ratio)
        assert max(spectrum[center-2:center+3])<max(original[center-2:center+3])*.001
    parts=np.concatenate([chime_note(age[i:i+613],220.,v) for i in range(0,len(age),613)])
    assert np.array_equal(parts,tuned)


def test_tuning_switch_changes_timbre_not_events_and_supports_live_playback(app,tmp_path):
    from synth_visual_sound_ui import VisualSoundDialog
    seq=study();c=seq['generated_sound'];c['chime_layer']['enabled']=True
    d=VisualSoundDialog();d.set_config(c);before=d.read_config()
    d.chime_layer.tuning.setCurrentIndex(d.chime_layer.tuning.findData('harmonic'))
    changed=d.read_config()
    assert changed['chime_layer']['chimes']['tuning']=='harmonic'
    assert changed['voices']==before['voices'] and changed['mixer']==before['mixer']
    d.undo_draft();assert d.read_config()==before
    d.redo_draft();assert d.read_config()==changed
    box=d.color_wave.voices['strum']['chime_tuning'];box.setCurrentIndex(box.findData('harmonic'))
    changed=d.read_config();assert changed['voices']['strum']['chimes']['tuning']=='harmonic'
    doc=lattice_composition();doc['generated_sound']=changed;save_composition(tmp_path/'tuned.json',doc)
    assert load_composition(tmp_path/'tuned.json')['generated_sound']==changed
    sig=visual_signals(seq);assert color_notes(sig,changed)==color_notes(sig,c)
    voice=ColorWaveVoice(seq,changed,sig);offline=voice.render(0,RATE)
    live=LiveInstrument(seq,sig,changed)
    assert np.array_equal(offline,np.concatenate([live.render(480) for _ in range(100)]))
    live.update(c);pcm=np.concatenate([live.render(480) for _ in range(6)])
    assert np.isfinite(pcm).all() and abs(np.diff(pcm,axis=0)).max()<.1
    d.close()
