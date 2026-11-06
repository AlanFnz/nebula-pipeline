import copy
import numpy as np
import pytest
from media import Cancellation
from synth_visual_sound import RATE,instrument_sound,normalize_sound
from synth_visual_sound_instrument import InstrumentVoice,instrument_blocks
from synth_visual_sound_live import LiveInstrument
from test_synth_visual_sound_instrument import signals


def loop_config():
    c=instrument_sound()
    c.update(seamless_loop=True,arp_mode='sequence',sequence_trigger='loop',sequence_length=16,
             pitch=80.63,arp_pitch=80.63,release=.41981,resonance=.9349,unison=2)
    return c


def test_repeated_pcm_keeps_note_tails_loudness_and_phase():
    c=loop_config();s=signals(2.);seq=dict(duration=2.,seed=12)
    s['expansion']=.5+.3*np.sin(s['time']*np.pi)
    voice=InstrumentVoice(seq,c,s);n=2*RATE
    audio=np.concatenate([voice.render(i,min(3571,2*n-i)) for i in range(0,2*n,3571)])
    # Warmed EQ/filter, whole-cycle drone phase and wrapped note seeds agree.
    assert np.max(abs(audio[:n]-audio[n:]))<1e-6
    assert abs(audio[n]-audio[n-1]).max()<np.quantile(abs(np.diff(audio,axis=0)),.999)
    rms=lambda a:np.sqrt(np.mean(a*a))
    assert rms(audio[:4800])>.01 and rms(audio[n-4800:n])>.01
    previous=[note for note in voice.notes if note['time']<0]
    assert previous and all('loop_index' in note for note in previous)
    offline=np.concatenate(list(instrument_blocks(seq,c,s,Cancellation(),block_size=RATE)))
    assert np.array_equal(audio[:n],offline)
    live=LiveInstrument(seq,s,c)
    repeated=np.concatenate([live.render(480) for _ in range(4*RATE//480)])
    assert np.array_equal(repeated,audio)


def test_loop_off_preserves_existing_pcm_and_validation():
    c=instrument_sound();legacy=copy.deepcopy(c);legacy.pop('seamless_loop')
    seq=dict(duration=1.,seed=12);s=signals(1.)
    assert np.array_equal(InstrumentVoice(seq,c,s).render(0,RATE),InstrumentVoice(seq,legacy,s).render(0,RATE))
    assert normalize_sound(legacy)['seamless_loop'] is False
    for value in (1,None,'true'):
        with pytest.raises(ValueError):normalize_sound(dict(c,seamless_loop=value))


def test_surface_clock_is_periodic_with_flow_and_both_projection_models():
    from synth import MODULE_BY_ID,normalize_synth
    from synth_pleated import render_pleated_field
    p={s.key:s.default for s in MODULE_BY_ID['pleated_field'].params}
    p.update(loop_seconds=20.,flow=.16)
    preset=normalize_synth();preset.update(width=160,height=120,speed=1.)
    image=np.zeros((120,160,3),np.float32)
    for projection in (0,1):
        p['projection']=projection
        first=render_pleated_field(image,p,0,preset)
        end=render_pleated_field(image,p,20,preset)
        assert np.array_equal(first,end)
        assert not np.array_equal(first,render_pleated_field(image,p,5,preset))


def test_study_closes_camera_and_preserves_user_settings():
    from synth_pleated_recipes import pleated_acid_composition
    from synth_pleated_loop import close_pleated_study
    from synth_performance import defaults,source_time
    from synth_composition import compile_composition
    from synth_sequence import resolve_sequence_frame
    project=pleated_acid_composition();project['visual_performance']=defaults()
    project['visual_performance']['values'].update(pace=78.62,relief=174.28,opening=63.64,texture=51.47)
    project['generated_sound'].update(unison=2,pitch=80.63)
    original=copy.deepcopy(project);loop=close_pleated_study(project)
    assert project==original
    assert loop['generated_sound']==dict(project['generated_sound'],seamless_loop=True)
    assert loop['visual_performance']['values']==dict(project['visual_performance']['values'],pace=100.,fluidity=0.)
    seq=compile_composition(loop);old=compile_composition(original)
    def camera(seq,t):return next(m['params'] for m in resolve_sequence_frame(seq,t)[-1]['modules'] if m['id']=='pleated_field')
    for frame in range(216):
        at=source_time(original['visual_performance'],frame/12,20,12)
        assert camera(seq,frame/12)==dict(camera(old,at),loop_seconds=20.)
    a,b=camera(seq,0),camera(seq,239/12)
    for key in ('angle','yaw','pitch','pan_x','pan_y','size','density'):
        assert abs(a[key]-b[key])<.03
    assert a['symmetry']==b['symmetry']==0 and seq['duration']==20


def test_sound_loop_checkbox_roundtrips_and_undoes(app):
    from synth_visual_sound_ui import VisualSoundDialog
    d=VisualSoundDialog();d.set_config(instrument_sound())
    d.seamless_loop.setChecked(True)
    assert d.read_config()['seamless_loop']
    d.undo_draft();assert not d.read_config()['seamless_loop']
    d.redo_draft();assert d.read_config()['seamless_loop']
    d.close()


from test_synth_visual_sound_ui import app
from test_synth_visual_sound_live import Output,monitors
from test_synth_composer_ui import wait_until


def test_transport_wrap_does_not_restart_audio_device(monitors):
    clock=[10.];monitor=monitors(backend_factory=Output,clock=lambda:clock[0])
    monitor.set_source(dict(duration=2.,seed=12),signals(2.),loop_config())
    monitor.sync(1.9,True);wait_until(lambda:monitor.backend is not None and len(monitor.backend.audio)>0)
    output=monitor.backend
    for _ in range(4):
        clock[0]+=.2;monitor.sync((1.9+clock[0]-10.)%2,True,force=True)
    assert output.starts==1
    clock[0]+=.1;monitor.sync(1.5,True)
    wait_until(lambda:output.starts==2)
