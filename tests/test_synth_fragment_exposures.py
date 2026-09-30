"""Reusable image fragments, opt-in tonal folds and preserved portrait recipes."""
import copy
import hashlib

import numpy as np
import pytest
from PIL import Image

import synth_chroma
from synth import MODULE_BY_ID, default_synth_preset, render_synth_frame
from synth_chroma import render_chroma_print, render_slice_echo
from synth_composition import compile_composition, load_composition, save_composition
from synth_portrait_recipes import fractured_composition, exposure_composition, portrait_composition
from synth_sequence import render_sequence_frame
from synth_video import apply_treatment, video_composition
from test_synth_video import clip
from test_synth_video_ui import window


def params(module, **changes):
    return dict({s.key:s.default for s in MODULE_BY_ID[module].params}, **changes)


def slices(arr, p, t=.21, seed=73, speed=1.):
    return render_slice_echo(arr,p,t,speed,seed,(arr.shape[1],arr.shape[0]))


def test_neutral_tonal_controls_keep_previous_float_pixels():
    arr=np.random.default_rng(192).random((61,97,3),dtype=np.float32)
    p=params('chroma_print',detail=1.7,solarize=.6)
    for settings in (p,{k:v for k,v in p.items() if k not in ('softness','solarize_lift')}):
        out=render_chroma_print(arr,settings,(97,61))
        assert hashlib.sha256(out.tobytes()).hexdigest() == '3e9dfcae54f8f40c328e471ccddd9c89b536773eafe6e49ddb08edb9fd0173f9'


def test_solarized_recovery_restores_white_and_retains_reversal():
    ramp=np.repeat(np.linspace(0,1,101,dtype=np.float32)[None,:,None],3,axis=2)
    p=params('chroma_print',exposure=0.,black=0.,white=1.,gamma=1.,
             mid_saturation=0.,white_saturation=0.,warm_color=0.,
             solarize=1.,solarize_point=.6,solarize_lift=1.)
    out=render_chroma_print(ramp,p,(101,1))
    assert out[0,60,0] == pytest.approx(1.)
    assert not out[0,0].any()
    assert out[0,99,0] < out[0,70,0] < out[0,60,0]
    p['solarize']=0.
    assert np.allclose(render_chroma_print(ramp,p,(101,1)),ramp)
    assert np.array_equal(render_chroma_print(ramp,dict(p,mix=0.),(101,1)),ramp)


def test_source_softness_reduces_input_detail_before_the_screen():
    image=np.zeros((90,90,3),dtype=np.float32);image[:,45:]=1.
    p=params('chroma_print',softness=8.,exposure=0.,black=0.,white=1.,gamma=1.,
             mid_saturation=0.,white_saturation=0.,warm_color=0.)
    out=render_chroma_print(image,p,(720,720))
    assert 0 < out[45,43,0] < out[45,47,0] < 1
    assert abs(out.mean()-.5) < .01


@pytest.mark.parametrize('shape', [(90,160),(160,90),(120,120)])
def test_fragments_are_bounded_and_edges_can_break_up(monkeypatch,shape):
    monkeypatch.setattr(synth_chroma,'slice_events',lambda *a: ((.5,.55,0.,0.,1.,True),))
    arr=np.full((*shape,3),.5,dtype=np.float32)
    p=params('slice_echo',width=.4,edge_breakup=0.,screen=0.,softness=0.,
             hue=0.,saturation=1.,color_mix=1.,opacity=1.)
    out=slices(arr,p);mask=np.abs(out[...,1]-arr[...,1])>.01
    assert mask.any() and not mask.all()
    assert mask.sum(axis=0).max() > 0
    assert mask.sum(axis=1).max() < shape[1]*.6
    broken=slices(arr,dict(p,edge_breakup=1.))
    broken_mask=broken[...,1]!=arr[...,1]
    assert not np.array_equal(mask,broken_mask)
    assert len(np.unique(broken_mask.sum(axis=0))) > 2
    # Changes are local: every pixel outside the image patch stays untouched.
    assert np.array_equal(broken[~broken_mask],arr[~broken_mask])


def test_fragment_layout_matches_across_preview_sizes(monkeypatch):
    monkeypatch.setattr(synth_chroma,'slice_events',lambda *a: ((.5,.5,0.,0.,1.,True),))
    p=params('slice_echo',width=.5,edge_breakup=.8,angle=-11.,softness=0.,
             hue=0.,saturation=1.,color_mix=1.,opacity=1.,screen=0.)
    masks=[]
    for size in (120,480):
        arr=np.full((size,size,3),.5,dtype=np.float32)
        out=slices(arr,p);mask=np.abs(out[...,1]-arr[...,1])>.01
        masks.append(np.asarray(Image.fromarray(np.uint8(mask)*255).resize((120,120),Image.Resampling.NEAREST))>128)
    assert np.mean(masks[0] != masks[1]) < .015


def test_fragment_clock_is_seeded_held_and_independent_of_request_order():
    arr=np.random.default_rng(9).random((80,110,3),dtype=np.float32)
    p=params('slice_echo',width=.45,edge_breakup=.8,negative=.9,activity=1.,cadence=10.,period=.7)
    out=slices(arr,p,.21)
    assert np.array_equal(out,slices(arr,p,.29))
    assert not np.array_equal(out,slices(arr,p,.31))
    assert not np.array_equal(out,slices(arr,p,.21,seed=74))
    slices(arr,p,90.)
    assert np.array_equal(out,slices(arr,p,.21))
    assert np.array_equal(slices(arr,p,0.,speed=0.),slices(arr,p,90.,speed=0.))
    assert np.array_equal(slices(arr,dict(p,mix=0.)),arr)


def test_negative_fragments_invert_image_tones_and_coverage_stays_source_based(monkeypatch):
    monkeypatch.setattr(synth_chroma,'slice_events',lambda *a: ((.5,3.,0.,0.,1.,False),))
    values=np.arange(256,dtype=np.float32)/255
    arr=np.repeat(values[None,:,None],3,axis=2)
    p=params('slice_echo',negative=1.,screen=0.,opacity=1.)
    out=slices(arr,p)
    assert np.allclose(out,1-arr,atol=1/255)
    p['luma_mask']=1.
    out=slices(arr,p)
    assert not out[0,0].any()
    assert np.isfinite(out).all()


@pytest.mark.parametrize('source', ['video','text','slab'])
def test_new_controls_work_for_all_source_adapters(source):
    p=default_synth_preset();p.update(width=120,height=90,speed=1.)
    for module in p['modules']:
        module['enabled']=module['id'] in (source,'slice_echo','chroma_print')
        if module['id']=='slice_echo':
            module['params'].update(width=.4,edge_breakup=.8,negative=.9,activity=1.,count=8)
        if module['id']=='chroma_print':
            module['params'].update(softness=1.,solarize=1.,solarize_lift=1.)
    image=Image.new('RGB',(120,90),'black');image.paste((230,145,80),(15,10,110,80))
    kwargs={'source_image':image} if source=='video' else {}
    out=render_synth_frame(p,time_seconds=.21,**kwargs)
    assert out.size==(120,90)
    assert out.tobytes()==render_synth_frame(p,time_seconds=.21,**kwargs).tobytes()
    for module in p['modules']:
        if module['id'] in ('slice_echo','chroma_print'):module['params']['mix']=0.
    assert out.tobytes()!=render_synth_frame(p,time_seconds=.21,**kwargs).tobytes()


def test_fractured_study_is_independent_portable_and_keeps_continuous_source(clip,tmp_path):
    originals=[portrait_composition(clip),exposure_composition(clip)]
    frozen=copy.deepcopy(originals)
    project=fractured_composition(clip)
    assert project['sections']==originals[1]['sections']
    assert project['footage']==originals[1]['footage']
    assert project['footage']['end_mode']=='hold'
    path=tmp_path/'study.json';save_composition(path,project)
    loaded=load_composition(path)
    first=render_sequence_frame(compile_composition(project),.21,(90,90))
    assert first.tobytes()==render_sequence_frame(compile_composition(loaded),.21,(90,90)).tobytes()
    project['effects']['slice_echo']['params']['slice_echo.width']=.9
    assert [portrait_composition(clip),exposure_composition(clip)]==frozen
    assert fractured_composition(clip)['effects']['slice_echo']['params']['slice_echo.width']==.44
    raw=video_composition(clip);raw['footage'].update(rotation=22.,x=17.,zoom=1.7)
    treated=apply_treatment(raw,7)
    for key in ('footage','sections','canvas'):assert treated[key]==raw[key]


def test_new_controls_edit_and_undo_in_native_inspector(window):
    panel=window.composer;panel.apply_video_treatment(7)
    effects=panel.effects_panel
    for effect,changes in [('slice_echo',dict(width=.25,edge_breakup=.9,negative=.95)),
                           ('chroma_print',dict(softness=2.,solarize_lift=.5))]:
        effects.inspect_effect(effect)
        for key,value in changes.items():
            path=f'{effect}.{key}';control=effects.controls[path].input;before=control.value()
            control.setValue(value)
            assert window.composition['effects'][effect]['params'][path]==value
            window.undo_composition()
            assert effects.controls[path].input.value()==before
