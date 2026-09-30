"""Editable typography and generic stretch/etch treatments share one pipeline."""
import copy

import numpy as np
import pytest
from PIL import Image

from synth import MODULE_BY_ID, render_synth_frame
from synth_canvas import resize_canvas
from synth_composition import compile_composition, save_composition, load_composition
from synth_echo import echo_scale, render_signal_etch, render_stretch_echo
from synth_sequence import render_sequence_frame
from synth_starters import starter_composition
from synth_text_recipes import opium_composition
from test_synth_text import source, extent


def params(module, **changes):
    return dict({s.key:s.default for s in MODULE_BY_ID[module].params}, **changes)


def test_effects_bypass_exactly_and_black_emits_no_light():
    arr = np.random.default_rng(8).random((60,80,3), dtype=np.float32)
    assert np.array_equal(arr, render_stretch_echo(arr, params('stretch_echo',mix=0.), .5, 1., (40,30), (80,60)))
    assert np.array_equal(arr, render_signal_etch(arr, params('signal_etch',mix=0.), .5, 1., 8, (80,60)))
    neutral = params('signal_etch', grain=0., erosion=0., roughness=0., scatter=0., pulse=0.)
    assert np.array_equal(arr, render_signal_etch(arr, neutral, .5, 1., 8, (80,60)))
    for time in (0., .3, 1.5):
        black = np.zeros_like(arr)
        assert not render_signal_etch(black,params('signal_etch'),time,1.,8,(80,60)).any()
        assert not render_stretch_echo(black,params('stretch_echo'),time,1.,(40,30),(80,60)).any()


def test_echo_motion_eases_resets_and_has_an_independent_hold_clock():
    p=params('stretch_echo',minimum=1.,stretch_y=4.,period=1.5,ease=3.)
    values=[echo_scale(p,t,1.) for t in (0.,.25,.5,.75)]
    assert values[0] == echo_scale(p,1.5,1.) == 1.
    assert all(a<b for a,b in zip(values,values[1:]))
    assert values[1]-values[0] > values[3]-values[2]
    assert echo_scale(dict(p,cadence=12.),.01,1.) == echo_scale(dict(p,cadence=12.),.07,1.)
    assert echo_scale(p,.01,1.) != echo_scale(p,.07,1.)
    assert echo_scale(p,.7,0.) == echo_scale(p,5.,0.)


def test_etch_is_repeatable_and_respects_texture_cadence_seed_and_pulses():
    arr=np.zeros((120,160,3),dtype=np.float32);arr[52:68,40:120]=1.
    def frame(t, seed=7, **changes):
        return render_signal_etch(arr,params('signal_etch',**changes),t,1.,seed,(160,120))
    assert np.array_equal(frame(.01,pulse=0.),frame(.03,pulse=0.))
    assert not np.array_equal(frame(.01),frame(.12))
    assert not np.array_equal(frame(.5),frame(.5,seed=8))
    assert np.array_equal(frame(.5),frame(.5))
    assert np.array_equal(frame(.3,cadence=0.,pulse=0.),frame(3.1,cadence=0.,pulse=0.))
    # A held texture isolates the repeating exposure envelope.
    assert np.allclose(frame(0,cadence=0.),frame(1.5,cadence=0.))
    assert frame(0,cadence=0.).sum() > frame(.7,cadence=0.).sum()


@pytest.mark.parametrize('effect', ['stretch_echo','signal_etch'])
def test_generic_effects_process_video_without_a_text_source(effect):
    p=source(); p.update(width=160,height=120)
    for m in p['modules']: m['enabled']=m['id']==effect
    image=Image.new('RGB',(160,120));image.paste((170,220,255),(60,50,100,70))
    frame=render_synth_frame(p,time_seconds=.5,source_image=image)
    assert frame.tobytes()!=image.tobytes()
    next(m for m in p['modules'] if m['id']==effect)['params']['mix']=0.
    assert render_synth_frame(p,time_seconds=.5,source_image=image).tobytes()==image.tobytes()


def test_echo_follows_object_and_canvas_without_stretching_the_group():
    p=source(fit=2,block_width=.6)
    for m in p['modules']:
        if m['id']=='stretch_echo': m.update(enabled=True,params=params('stretch_echo',motion=0,typeface=4,outline=0.))
    initial=extent(render_synth_frame(p))
    q=copy.deepcopy(p);q.update(resize_canvas(p,{'width':600,'height':800}));q.update(object_x=25.,object_y=-20.)
    assert extent(render_synth_frame(q))==tuple(v+d for v,d in zip(initial,(125,230,125,230)))


def test_opium_is_frozen_portable_and_wording_remains_editable(tmp_path):
    p=starter_composition('text-opium')
    assert p==opium_composition()
    seq=compile_composition(p)
    assert seq['duration']==4.5 and seq['fps']==24
    initial=render_sequence_frame(seq,.7,(240,300))
    p['effects']['text']={'mode':'recipe','params':{'text.content':'SIGNAL'}}
    p['effects']['stretch_echo']={'mode':'recipe','params':{'stretch_echo.stretch_y':2.5}}
    path=tmp_path/'opium.json';save_composition(path,p)
    loaded=load_composition(path)
    changed=render_sequence_frame(compile_composition(loaded),.7,(240,300))
    assert changed.tobytes()!=initial.tobytes()
    assert loaded==p
    assert starter_composition('text-opium')==opium_composition()


def test_pulse_extent_stays_stable_while_echo_opens():
    base=np.zeros((120,160,3),dtype=np.float32);base[53:67,40:120]=1.
    p=params('signal_etch',grain=0.,erosion=0.,roughness=0.,scatter=0.,core=0.,cadence=0.,pulse_stretch=2.8)
    # Identical pulse source/time means changing the echo cannot grow the flash.
    tall=base.copy();tall[20:100,60:62]=1.
    a=render_signal_etch(base,p,0.,1.,7,(160,120),base)-base
    b=render_signal_etch(tall,p,0.,1.,7,(160,120),base)-tall
    assert np.allclose(a,b,atol=1e-6)
