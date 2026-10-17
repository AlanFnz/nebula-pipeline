import copy
import subprocess

import numpy as np
import pytest

from synth import MODULE_BY_ID, curated_presets, default_synth_preset, render_synth_frame
from synth_canvas import resize_canvas
from synth_composition import compile_composition, save_composition, load_composition
from synth_effect_catalog import effect_catalog
from synth_effects import describe_effects
from synth_memory import render_image_memory, memory_pose, memory_frame, MAX_TRACES
from synth_memory_recipes import memory_composition
from synth_sequence import render_sequence_frame, resolve_sequence_frame
from synth_source_adapters import source_frame
from synth_starters import starter_composition
from synth_studies import composition_category
from synth_subject import active_subjects, scope_states, select_subject


def defaults():
    return {p.key: p.default for p in MODULE_BY_ID['image_memory'].params}


def render(p=None, t=7., size=(96,128), **settings):
    p = defaults() if p is None else p
    preset = dict(default_synth_preset(), width=size[0], height=size[1], speed=1., **settings)
    return render_image_memory(np.zeros((size[1],size[0],3),np.float32), p, t, preset)


def test_recipe_is_portable_independent_and_seekable(tmp_path):
    project = starter_composition('image-memory')
    authored = compile_composition(memory_composition())
    assert composition_category(project) == 'Signals'
    assert active_subjects(describe_effects(scope_states(project))) == ('memory',)
    assert 'image_memory' not in {item.id for item in effect_catalog()}
    seq = compile_composition(project)
    assert seq['duration'] == 15 and seq['fps'] == 24
    assert (seq['canvas']['width'],seq['canvas']['height']) == (720,960)
    before = copy.deepcopy(project)
    frames = {t: render_sequence_frame(seq,t,(96,128)).tobytes() for t in (0.,3.,7.2,14.9)}
    # New disabled controls may be explicit in the factory and absent from the
    # frozen document. Their rendered contract must still agree exactly.
    for t, pixels in frames.items():
        assert render_sequence_frame(authored,t,(96,128)).tobytes() == pixels
    for t in (14.9,7.2,0.,3.,7.2):
        assert render_sequence_frame(seq,t,(96,128)).tobytes() == frames[t]
    save_composition(tmp_path/'study.json',project)
    restored = compile_composition(load_composition(tmp_path/'study.json'))
    assert render_sequence_frame(restored,7.2,(96,128)).tobytes() == frames[7.2]
    assert project == before
    assert active_subjects(describe_effects(scope_states(select_subject(project,'none')))) == ()
    text = select_subject(project,'text')
    assert active_subjects(describe_effects(scope_states(text))) == ('text',)
    assert describe_effects(scope_states(text))['film_emulsion']['active']


@pytest.mark.parametrize('shape,sides', [(0,5),(1,5),(2,3),(2,4),(2,12)])
@pytest.mark.parametrize('size', [(64,160),(173,65)])
def test_extremes_are_bounded_finite_and_do_not_mutate(shape,sides,size):
    p = dict(defaults(),shape=shape,sides=sides,size=.6,persistence=12.,
             drift=1.,dissolve=1.,expansion=1.,period=2.,travel=1.)
    for time in (0.,.01,3.,37.,3600.):
        result = render(p,time,size)
        assert result.shape == (size[1],size[0],3)
        assert np.isfinite(result).all() and 0 <= result.min() <= result.max() <= 1
    arr = np.full((size[1],size[0],3),.25,np.float32)
    before = arr.copy()
    render_image_memory(arr,p,4.,default_synth_preset())
    assert np.array_equal(arr,before)
    assert render_image_memory(arr,dict(p,mix=0),4.,default_synth_preset()) is arr


def test_zero_history_and_zero_trace_strength_leave_the_same_current_object():
    p = dict(defaults(),persistence=0.)
    assert np.array_equal(render(p),render(dict(defaults(),trail_opacity=0.)))
    assert np.array_equal(render(p),render(dict(p,drift=1.,dissolve=1.,expansion=1.)))
    # History starts with the piece, with no fabricated pre-roll.
    assert np.array_equal(render(t=0.),render(p,t=0.))
    assert np.mean(np.abs(render(t=7.)-render(p,t=7.))) > .01


@pytest.mark.parametrize('change', [dict(drift=0.),dict(dissolve=0.),dict(persistence=2.),
    dict(palette=1),dict(shape=0),dict(shape=2,sides=3),dict(path=0),dict(travel=0.),
    dict(period=3.),dict(expansion=-.5),dict(color_shift=0.)])
def test_exploration_controls_have_independent_visible_effects(change):
    assert np.mean(np.abs(render()-render(dict(defaults(),**change)))) > .0003


def test_continuous_motion_and_history_births_do_not_pop():
    p = dict(defaults(),softness=0,glow=0)
    for t in (0.,.35,3.,p['persistence'],15.):
        # Close adjacent times across birth/death boundaries; no hidden state.
        assert np.mean(np.abs(render(p,t)-render(p,t+.001))) < .002
    for path in range(3):
        q = dict(p,path=path)
        poses = np.array([memory_pose(q,t)[:2] for t in np.linspace(0,30,3001)])
        assert np.max(np.abs(np.diff(poses,axis=0))) < .02
        still = dict(q,travel=0.)
        assert memory_pose(still,0)[:2] == memory_pose(still,19)[:2] == (0.,0.)


@pytest.mark.parametrize('path', range(3))
def test_motion_amplitudes_scale_only_the_requested_axis(path):
    p = dict(defaults(), path=path)
    preset = dict(default_synth_preset(), width=144, height=192, speed=1., object_x=17., object_y=-9.)
    for t in (0., 1.3, 7., 19.):
        x, y, angle = memory_pose(p, t)
        assert memory_pose(dict(p, amplitude_x=0.), t) == (0., y, angle)
        assert memory_pose(dict(p, amplitude_y=0.), t) == (x, 0., angle)
        assert memory_pose(dict(p, amplitude_x=200., amplitude_y=50.), t) == (x*2, y*.5, angle)
        center, radius, rotation = memory_frame(p, (144,192), t, preset)
        fixed, same_radius, same_rotation = memory_frame(dict(p, amplitude_x=0., amplitude_y=0.), (144,192), t, preset)
        assert fixed == (89., 87.)
        assert (same_radius, same_rotation) == (radius, rotation)
    # Frozen recipes omit the new controls; neutral values preserve every pixel.
    legacy = {k:v for k,v in p.items() if not k.startswith('amplitude_')}
    assert np.array_equal(render(legacy), render(p))


def test_amplitudes_reposition_history_without_scaling_shapes_or_drift(monkeypatch):
    import synth_memory
    calls = []
    monkeypatch.setattr(synth_memory, '_stamp', lambda canvas, center, radius, *args: calls.append((center, radius)))
    p = dict(defaults(), drift=0.)
    render(p); original = list(calls); calls.clear()
    render(dict(p, amplitude_x=0., amplitude_y=50.)); narrowed = list(calls); calls.clear()
    assert len(original) == len(narrowed) > 1
    for ((x,y),radius), ((nx,ny),nradius) in zip(original,narrowed):
        assert nx == 48. and ny == pytest.approx(64.+(y-64.)*.5)
        assert nradius == radius
    render(dict(p, amplitude_x=0., amplitude_y=0., drift=.5, drift_angle=0.))
    assert all(center[1] == 64. for center,_ in calls)
    assert any(center[0] > 48. for center,_ in calls[:-1])
    assert calls[-1][0] == (48.,64.)


def test_sample_work_is_bounded_and_neutral_history_skips_it(monkeypatch):
    import synth_memory
    calls=[]
    monkeypatch.setattr(synth_memory,'_stamp',lambda *args: calls.append(1))
    render(t=3600.)
    assert 1 < len(calls) <= MAX_TRACES+1
    calls.clear();render(dict(defaults(),persistence=0.))
    assert len(calls)==1


def test_source_clock_and_seed_are_deterministic():
    p=defaults()
    a=render(p,5.,seed=100)
    assert np.array_equal(a,render(p,5.,seed=100))
    assert not np.array_equal(a,render(p,5.,seed=101))
    preset=dict(default_synth_preset(),width=96,height=128,speed=0.)
    arr=np.zeros((128,96,3),np.float32)
    assert np.array_equal(render_image_memory(arr,p,0,preset),render_image_memory(arr,p,20,preset))
    preset['speed']=2
    assert np.array_equal(render(p,6.),render_image_memory(arr,p,3.,preset))


def test_reframing_and_anchor_preserve_artwork_geometry():
    p=resolve_sequence_frame(compile_composition(memory_composition()),0)[-1]
    p.update(width=144,height=192)
    for m in p['modules']:
        m['enabled']=m['id']=='image_memory'
        if m['id']=='image_memory': m['params'].update(softness=0.,glow=0.)
    wide=copy.deepcopy(p); wide.update(resize_canvas(p,dict(width=244,height=192)))
    a=np.asarray(render_synth_frame(p,time_seconds=4.))
    b=np.asarray(render_synth_frame(wide,time_seconds=4.))
    assert np.array_equal(a,b[:,50:194])
    module=next(m for m in p['modules'] if m['id']=='image_memory')
    center,radius,angle=memory_frame(module['params'],(144,192),4.,p)
    anchor=source_frame(p,(144,192),4.)
    explicit=source_frame(p,(144,192),0.,'image_memory',4.)
    assert anchor==explicit
    assert anchor.origin==pytest.approx(center)
    moved=source_frame(dict(p,object_x=20,object_y=-10),(144,192),4.)
    assert moved.origin==pytest.approx((center[0]+20,center[1]-10))


def test_existing_presets_leave_the_new_source_disabled():
    for preset in curated_presets().values():
        assert not next(m for m in preset['modules'] if m['id']=='image_memory')['enabled']


def test_short_export_agrees_with_preview(tmp_path):
    from synth_media import export_synth_video
    seq=compile_composition(memory_composition());seq['duration']=1.;seq['fps']=12
    output=export_synth_video(default_synth_preset(),tmp_path/'memory.mp4',sequence=seq,size=(96,128))
    data=subprocess.run(['ffmpeg','-v','error','-i',str(output),'-f','rawvideo','-pix_fmt','rgb24','pipe:1'],capture_output=True,check=True).stdout
    frames=np.frombuffer(data,dtype=np.uint8).reshape((-1,128,96,3))
    assert len(frames)==12
    for i in (0,5,11):
        expected=np.asarray(render_sequence_frame(seq,i/12,(96,128)))
        assert np.mean(np.abs(expected.astype(float)-frames[i])) < 6
