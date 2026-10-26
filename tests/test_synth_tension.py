"""Elastic image treatment: input independence, timing and rendering contract."""
import copy
import subprocess

import numpy as np
from PIL import Image
import pytest

import synth
from synth import MODULE_BY_ID, default_synth_preset, render_synth_frame
from synth_composition import compile_composition, save_composition, load_composition
from synth_effect_catalog import effect_catalog
from synth_effect_order import movable
from synth_effects import effect_preset
from synth_sequence import render_sequence_frame
from synth_starters import starter_composition
from synth_subject import select_subject
from synth_tension import render_signal_tension, gesture, MAX_ECHOES
from synth_tension_recipes import tension_composition
from synth_video import VIDEO_EFFECTS, VIDEO_MODULES


def defaults(**changes):
    return {**{p.key:p.default for p in MODULE_BY_ID['signal_tension'].params},**changes}


def source(size=(96,72)):
    w,h=size; yy,xx=np.mgrid[:h,:w]
    result=np.full((h,w,3),.06,np.float32)
    result[(xx-w*.5)**2+(yy-h*.5)**2 < (h*.22)**2]=(.9,.75,.5)
    return result


def render(p=None,t=2.5,arr=None,seed=90,speed=1.):
    arr=source() if arr is None else arr
    return render_signal_tension(arr,p or defaults(),t,speed,seed,(arr.shape[1],arr.shape[0]))


def test_frozen_study_is_independent_portable_and_seekable(tmp_path):
    project=starter_composition('tension');before=copy.deepcopy(project)
    seq=compile_composition(project); factory=compile_composition(tension_composition())
    assert seq['duration']==15 and seq['fps']==24
    assert seq['canvas']=={'width':960,'height':720,'framing':'native'}
    assert 'signal_tension' in {e.id for e in effect_catalog()}
    assert movable('signal_tension') and 'signal_tension' in VIDEO_EFFECTS and 'signal_tension' in VIDEO_MODULES
    frames={t:render_sequence_frame(seq,t,(96,72)).tobytes() for t in (0.,2.5,7.8,14.95)}
    for t in (14.95,2.5,0.,7.8):
        assert render_sequence_frame(seq,t,(96,72)).tobytes()==frames[t]
        assert render_sequence_frame(factory,t,(96,72)).tobytes()==frames[t]
    save_composition(tmp_path/'tension.json',project)
    assert load_composition(tmp_path/'tension.json')==project==before
    project['effects']['signal_tension']=effect_preset('signal_tension')
    project['effects']['signal_tension']['params']['signal_tension.tension']=0
    assert starter_composition('tension')==before


def test_neutral_and_dark_signal_do_not_fabricate_content_or_mutate_input():
    arr=source(); before=arr.copy()
    assert render(defaults(tension=0),arr=arr) is arr
    for value in (0.,.04,.18):
        quiet=np.full_like(arr,value)
        assert render(arr=quiet) is quiet
    actual=render(arr=arr)
    assert np.array_equal(arr,before)
    assert np.mean(np.abs(actual-arr))>.005


@pytest.mark.parametrize('shape',[(1,1),(64,20),(21,79),(96,72)])
@pytest.mark.parametrize('region',[0,1])
def test_extreme_parameters_are_finite_and_bounded(shape,region):
    arr=source(shape)
    p=defaults(tension=1.,cohesion=0.,persistence=4.,instability=1.,texture=1.,
               direction=173.,spacing=3.,bend=1.,period=1.5,timing=1.,region=region)
    for t in (0.,.001,3.,3600.):
        actual=render(p,t,arr)
        assert actual.shape==arr.shape and actual.dtype==np.float32
        assert np.isfinite(actual).all() and 0<=actual.min()<=actual.max()<=1


def test_motion_is_continuous_at_jittered_gesture_boundaries_and_has_unequal_holds():
    p=defaults(texture=0.,persistence=0.)
    times=np.arange(0,30,.002)
    forces=np.array([gesture(p,t,90)[0] for t in times])
    assert np.max(abs(np.diff(forces)))<.01
    # Three releases have distinct onset spacing with timing variation enabled.
    starts=times[1:][(forces[:-1]<.4)&(forces[1:]>=.4)]
    assert len(starts)>=4 and np.ptp(np.diff(starts))>.2
    for t in (0.,.3,2.5,4.6,9.2):
        assert np.mean(abs(render(p,t)-render(p,t+.0001)))<.001
    fixed=defaults(timing=0.)
    for t in (.1,1.,2.,3.,4.):
        assert gesture(fixed,t,90)[0]==pytest.approx(gesture(fixed,t+fixed['period'],90)[0])


@pytest.mark.parametrize('change',[dict(tension=.3),dict(cohesion=1.),dict(persistence=0.),
    dict(instability=0.),dict(texture=0.),dict(direction=90.),dict(spacing=18.),dict(bend=0.),dict(palette=2)])
def test_exploration_controls_visibly_change_the_result(change):
    assert np.mean(np.abs(render()-render(defaults(**change))))>.0001


def test_clock_seed_and_echo_sampling_are_bounded(monkeypatch):
    import synth_tension
    p=defaults()
    assert np.array_equal(render(p,2.),render(p,1.,speed=2.))
    assert np.array_equal(render(p,0.),render(p,5.,speed=0.))
    assert not np.array_equal(render(seed=90),render(seed=91))
    calls=[]; sample=synth_tension._sample
    def record(*args): calls.append(1); return sample(*args)
    monkeypatch.setattr(synth_tension,'_sample',record)
    render(t=3600.)
    assert len(calls)==MAX_ECHOES+1
    calls.clear(); render(defaults(persistence=0.))
    assert len(calls)==1


@pytest.mark.parametrize('ordered',[False,True])
def test_reusable_pass_supports_text_video_and_independent_intensity(ordered):
    project=select_subject(tension_composition(),'text')
    project['effects']['text']['params'].update({'text.content':'REVOLUTION\nIS NOW','text.size':.32})
    seq=compile_composition(project)
    text=render_sequence_frame(seq,2.5,(96,72))
    assert np.asarray(text).std()>15
    p=default_synth_preset();p.update(speed=1.,depth=0.)
    for entry in p['modules']:entry['enabled']=entry['id']=='signal_tension'
    if ordered:p['effect_order']=['signal_tension']
    params=next(m['params'] for m in p['modules'] if m['id']=='signal_tension')
    frame=Image.fromarray(np.uint8(source()*255))
    params['effect_intensity']=100
    full=np.asarray(render_synth_frame(p,time_seconds=2.5,size=frame.size,source_image=frame)).astype(float)
    params['effect_intensity']=0
    dry=np.asarray(render_synth_frame(p,time_seconds=2.5,size=frame.size,source_image=frame)).astype(float)
    assert np.array_equal(dry,np.asarray(frame))
    params['effect_intensity']=50
    half=np.asarray(render_synth_frame(p,time_seconds=2.5,size=frame.size,source_image=frame))
    assert np.max(abs(half-(full+dry)/2))<=1
    assert np.mean(abs(full-dry))>1


def test_pass_order_and_next_finish_receive_the_complete_treated_image(monkeypatch):
    p=default_synth_preset()
    for m in p['modules']:m['enabled']=m['id'] in ('signal_tension','broadcast')
    monkeypatch.setattr(synth,'render_signal_tension',lambda arr,*args:arr+.3)
    monkeypatch.setitem(synth.RENDERERS,'broadcast',lambda arr,*args:arr*.5)
    p['effect_order']=['signal_tension','broadcast']
    first=np.asarray(render_synth_frame(p,size=(48,36))).astype(float)
    p['effect_order'].reverse()
    second=np.asarray(render_synth_frame(p,size=(48,36))).astype(float)
    assert np.max(abs(second-first-.15*255))<=1


def test_short_export_matches_preview(tmp_path):
    from synth_media import export_synth_video
    seq=compile_composition(tension_composition());seq['duration']=3.;seq['fps']=6
    out=export_synth_video(default_synth_preset(),tmp_path/'tension.mp4',sequence=seq,size=(128,96))
    raw=subprocess.run(['ffmpeg','-v','error','-i',str(out),'-f','rawvideo','-pix_fmt','rgb24','pipe:1'],capture_output=True,check=True).stdout
    frames=np.frombuffer(raw,np.uint8).reshape((-1,96,128,3))
    assert len(frames)==18
    for frame in (0,10,15,17):
        expected=np.asarray(render_sequence_frame(seq,frame/6,(128,96))).astype(float)
        assert np.mean(abs(frames[frame]-expected))<5
