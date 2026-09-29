"""Reusable source treatments, held clocks and the local portrait recipe."""
import copy

import numpy as np
import pytest
from PIL import Image

from synth import MODULE_BY_ID, curated_presets, default_synth_preset, render_synth_frame
from synth_chroma import render_chroma_print, render_slice_echo, render_screen_mesh, slice_events
from synth_composition import compile_composition
from synth_portrait_recipes import PORTRAIT_EFFECTS, portrait_composition
from synth_sequence import render_sequence_frame
from synth_studies import save_study, study_composition
from synth_video import TREATMENTS, apply_treatment, source_index, video_composition
from test_synth_video import clip


def params(module, **changes):
    return dict({s.key:s.default for s in MODULE_BY_ID[module].params}, **changes)


def apply(module, image, time=.4, speed=1., seed=31, **changes):
    p = params(module, **changes)
    size = (image.shape[1], image.shape[0])
    if module == 'chroma_print': return render_chroma_print(image, p, size)
    renderer = render_slice_echo if module == 'slice_echo' else render_screen_mesh
    return renderer(image, p, time, speed, seed, size)


@pytest.mark.parametrize('module', ['chroma_print', 'slice_echo', 'screen_mesh'])
def test_mix_zero_is_exact_and_black_does_not_emit_light(module):
    image = np.random.default_rng(7).random((90,120,3), dtype=np.float32)
    assert np.array_equal(apply(module,image,mix=0.),image)
    for t in (0.,.4,1.1):
        assert not apply(module,np.zeros_like(image),time=t).any()


def test_chroma_preserves_relief_and_exposes_independent_palette_controls():
    ramp = np.repeat(np.linspace(0,1,128,dtype=np.float32)[None,:,None],3,axis=2)
    gray = apply('chroma_print',ramp,exposure=0.,black=0.,white=1.,gamma=1.,
                 mid_saturation=0.,white_saturation=0.,warm_color=0.)
    assert np.allclose(gray,ramp)
    cyan = apply('chroma_print',ramp,mid_hue=.5,mid_saturation=1.,white_saturation=0.)
    assert cyan[0,50,1] > cyan[0,50,0]
    assert np.ptp(cyan[0,-1]) == 0
    red = np.full((20,20,3),(.8,.3,.1),dtype=np.float32)
    a = apply('chroma_print',red,warm_color=0.)
    b = apply('chroma_print',red,warm_color=1.,warm_threshold=0.,warm_hue=.9)
    assert not np.array_equal(a,b)
    extremes = apply('chroma_print',ramp,detail=4.,black=.8,white=.2,solarize=1.)
    assert np.isfinite(extremes).all()


def test_slice_layout_is_deterministic_with_independent_hold_and_freeze_clocks():
    p = params('slice_echo',activity=1.,cadence=10.)
    first = slice_events(p,.21,1.,9)
    assert first == slice_events(p,.29,1.,9)
    assert first != slice_events(p,.31,1.,9)
    assert first != slice_events(p,.21,1.,10)
    slice_events(p,90.,1.,9)
    assert first == slice_events(p,.21,1.,9)
    assert slice_events(p,2.,0.,9) == slice_events(p,0.,0.,9)
    assert slice_events(dict(p,activity=0.),.21,1.,9) == ()
    p['cadence'] = 0.
    assert slice_events(p,.21,1.,9) != slice_events(p,.22,1.,9)


def test_slices_reuse_actual_source_and_do_not_paint_independent_bars():
    image = np.zeros((120,160,3),dtype=np.float32)
    image[20:100,20:140] = (1.,.5,.25)
    out = apply('slice_echo',image,count=12,activity=1.,color_chance=0.,
                opacity=1.,screen=0.,shift_x=.5,shift_y=.3,scale=.2)
    assert not np.array_equal(image,out)
    # Displaced source retains its hue, including across interpolated edges.
    assert np.abs(out[...,0]-2*out[...,1]).max() < .009
    # Conversion and bilinear resampling each quantize to eight-bit channels.
    assert np.abs(out[...,0]-4*out[...,2]).max() <= 5/255 + 1e-6
    assert np.array_equal(apply('slice_echo',image,activity=0.),image)


def test_screen_clock_holds_all_texture_and_keeps_mean_exposure_at_preview_sizes():
    image = np.full((90,120,3),.5,dtype=np.float32)
    assert np.array_equal(apply('screen_mesh',image,time=.201,bend=2.),
                          apply('screen_mesh',image,time=.239,bend=2.))
    assert np.array_equal(apply('screen_mesh',image,time=0.,cadence=0.,bend=2.),
                          apply('screen_mesh',image,time=10.,cadence=0.,bend=2.))
    assert not np.array_equal(apply('screen_mesh',image,time=.2),
                              apply('screen_mesh',image,time=.4))
    means = []
    for edge in (180,360,720):
        uniform = np.full((edge,edge,3),.5,dtype=np.float32)
        out = apply('screen_mesh',uniform,grain=0.,softness=0.,angle=7.,jitter=0.)
        means.append(out.mean(axis=(0,1),dtype=np.float64))
    assert np.max(np.abs(np.array(means)-means[-1])) < .002


@pytest.mark.parametrize('module', ['chroma_print', 'slice_echo', 'screen_mesh'])
def test_effects_are_opt_in_for_old_presets_and_work_on_video_pixels(module):
    for p in [default_synth_preset(), *curated_presets().values()]:
        assert not next(m for m in p['modules'] if m['id']==module)['enabled']
    p = default_synth_preset(); p.update(width=120,height=90)
    for m in p['modules']:
        m['enabled'] = m['id']==module
        if m['id']=='slice_echo': m['params'].update(activity=1.,count=12)
    image = Image.new('RGB',(120,90),(0,0,0)); image.paste((200,180,130),(20,20,100,70))
    result = render_synth_frame(p,time_seconds=.4,source_image=image)
    assert result.tobytes() != image.tobytes()
    assert result.tobytes() == render_synth_frame(p,time_seconds=.4,source_image=image).tobytes()
    next(m for m in p['modules'] if m['id']==module)['params']['mix'] = 0.
    assert render_synth_frame(p,time_seconds=.4,source_image=image).tobytes() == image.tobytes()


def test_new_treatment_keeps_framing_source_and_timeline(clip):
    p = video_composition(clip); p['footage'].update(x=8.,y=-9.,zoom=1.2)
    before = copy.deepcopy(p)
    assert [name for name,_ in TREATMENTS[:5]] == [
        'Clean / start from source','Worn tape','Printed motion','Soft signal','Cold photocopy']
    treated = apply_treatment(p,5)
    assert p == before
    for key in ('footage','sections','canvas'): assert treated[key] == p[key]
    assert set(treated['effects']) == set(PORTRAIT_EFFECTS)
    assert render_sequence_frame(compile_composition(treated),.4,(96,72)).size == (96,72)


def test_portrait_study_freezes_controls_copies_media_and_uses_source_once(clip,tmp_path):
    p = portrait_composition(clip)
    assert len(p['sections']) == 1
    assert p['sections'][0]['duration'] == clip['out']-clip['in']
    assert p['footage']['end_mode'] == 'hold'
    seq = compile_composition(p)
    assert [source_index(seq['footage'],i/12) for i in range(12)] == list(range(12))
    for effect in PORTRAIT_EFFECTS:
        assert set(p['effects'][effect]['params']) == {f'{effect}.{s.key}' for s in MODULE_BY_ID[effect].params}
    saved = save_study(p,p['name'],tmp_path)
    restored = study_composition(saved,tmp_path)
    assert restored['footage']['path'] != clip['path']
    for t in (.1,.5,.9):
        assert render_sequence_frame(seq,t,(96,96)).tobytes() == render_sequence_frame(
            compile_composition(restored),t,(96,96)).tobytes()
