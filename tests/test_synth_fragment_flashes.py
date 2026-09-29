"""Short square exposures can coexist with slower full-width bars."""
import copy

import numpy as np
import pytest

import synth_chroma
from synth import MODULE_BY_ID
from synth_chroma import render_slice_echo
from synth_composition import compile_composition,load_composition,save_composition
from synth_portrait_recipes import crt_bars_composition,exposure_composition,fractured_composition
from synth_sequence import render_sequence_frame
from synth_video import apply_treatment
from test_synth_video import clip
from test_synth_video_ui import window


def params(**changes):
    return dict({s.key:s.default for s in MODULE_BY_ID['slice_echo'].params},**changes)


def render(arr,p,t=0.,seed=7,speed=1.):
    return render_slice_echo(arr,p,t,speed,seed,(arr.shape[1],arr.shape[0]))


def test_disabled_or_missing_flashes_preserve_old_pass():
    arr=np.random.default_rng(14).random((91,127,3),dtype=np.float32)
    p=params(activity=1.,count=5,width=.4,edge_breakup=.5,negative=.8,envelope=.13)
    legacy={k:v for k,v in p.items() if not k.startswith('flash_')}
    for t in (0.,.21,1.23):
        expected=synth_chroma._render_slice_pass(arr,legacy,t,1.,7,(127,91))
        assert np.array_equal(render(arr,p,t),expected)
        assert np.array_equal(render(arr,legacy,t),expected)


def test_flash_only_has_a_short_fade_and_separate_interval(monkeypatch):
    monkeypatch.setattr(synth_chroma,'slice_events',lambda *a: ((.5,3.,0.,0.,1.,True),))
    arr=np.full((80,80,3),.6,dtype=np.float32)
    p=params(opacity=0.,flash_opacity=.25,flash_seconds=.06,flash_period=.18,
             flash_width=1.,flash_height=1.,flash_breakup=0.,flash_negative=0.,
             cadence=0.,hue=0.,saturation=1.,color_mix=1.,screen=0.)
    peak=render(arr,p,0.);half=render(arr,p,.03)
    assert not np.array_equal(peak,arr)
    assert np.max(np.abs(peak-arr)) <= .25+1e-6
    assert np.mean(np.abs(half-arr)) < np.mean(np.abs(peak-arr))
    assert np.array_equal(render(arr,p,.07),arr)
    assert np.array_equal(render(arr,p,.17),arr)
    assert np.array_equal(render(arr,p,.18),peak)
    assert np.array_equal(render(arr,dict(p,period=3.),0.),peak)
    # The whole-effect Mix blends the composed bars/flashes once.
    assert np.allclose(render(arr,dict(p,mix=.4),0.),arr*.6+peak*.4)
    assert np.array_equal(render(arr,dict(p,mix=0.),0.),arr)


def test_flashes_follow_held_clock_seed_and_freeze_without_changing_main_bars():
    arr=np.random.default_rng(9).random((83,117,3),dtype=np.float32)
    p=params(flash_opacity=.4,flash_period=.2,flash_seconds=.06,cadence=25.,activity=1.)
    first=render(arr,p,.20)
    assert np.array_equal(first,render(arr,p,.23))
    assert not np.array_equal(first,render(arr,p,.20,seed=8))
    render(arr,p,200.)
    assert np.array_equal(first,render(arr,p,.20))
    assert np.array_equal(render(arr,p,0.,speed=0.),render(arr,p,50.,speed=0.))
    # Between flashes, the primary pass has precisely the same pixels.
    assert np.array_equal(render(arr,p,.12),render(arr,dict(p,flash_opacity=0.),.12))


@pytest.mark.parametrize('shape',[(100,100),(160,90),(90,160)])
def test_flash_extremes_are_finite_and_duration_is_capped(shape):
    arr=np.random.default_rng(91).random((*shape,3),dtype=np.float32)
    p=params(flash_opacity=1.,flash_period=.05,flash_seconds=2.,flash_count=6,
             flash_width=.05,flash_height=1.,flash_breakup=1.,flash_negative=1.,activity=1.)
    out=render(arr,p,.04)
    assert out.shape==arr.shape and np.isfinite(out).all()
    assert np.array_equal(out,render(arr,dict(p,flash_seconds=.05),.04))


def test_bars_recipe_preserves_bars_and_crt_with_portable_independent_flashes(clip,tmp_path):
    old=exposure_composition(clip);crt=fractured_composition(clip)
    frozen=copy.deepcopy((old,crt));p=crt_bars_composition(clip)
    for key,value in p['effects']['slice_echo']['params'].items():
        if not key.startswith('slice_echo.flash_'):assert value==old['effects']['slice_echo']['params'][key]
    for fx in p['effects']:
        if fx!='slice_echo':assert p['effects'][fx]==crt['effects'][fx]
    assert p['footage']==old['footage'] and p['sections']==old['sections']
    assert p['effects']['slice_echo']['params']['slice_echo.flash_opacity'] < .3
    assert p['effects']['slice_echo']['params']['slice_echo.flash_seconds'] < .1
    path=tmp_path/'bars.json';save_composition(path,p)
    loaded=load_composition(path)
    first=render_sequence_frame(compile_composition(p),.2,(90,90))
    assert first.tobytes()==render_sequence_frame(compile_composition(loaded),.2,(90,90)).tobytes()
    treated=apply_treatment(p,8)
    for key in ('footage','sections','canvas'):assert treated[key]==p[key]
    p['effects']['slice_echo']['params']['slice_echo.flash_opacity']=.9
    assert (exposure_composition(clip),fractured_composition(clip))==frozen


def test_native_flash_controls_edit_and_undo(window):
    panel=window.composer;panel.apply_video_treatment(8)
    effects=panel.effects_panel;effects.inspect_effect('slice_echo')
    for key,value in [('flash_opacity',.18),('flash_period',.25),('flash_seconds',.04),
                      ('flash_count',1),('flash_width',.4),('flash_height',.3),
                      ('flash_breakup',.5),('flash_negative',.1)]:
        path=f'slice_echo.{key}';control=effects.controls[path].input;before=control.value()
        control.setValue(value)
        assert window.composition['effects']['slice_echo']['params'][path]==value
        window.undo_composition()
        assert effects.controls[path].input.value()==before
