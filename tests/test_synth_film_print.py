"""New print passes are optional, editable and independent of seek history."""
import copy

import numpy as np
import pytest
from PIL import Image

from synth import MODULE_BY_ID, curated_presets, default_synth_preset, render_synth_frame
from synth_composition import compile_composition, load_composition, save_composition
from synth_effect_catalog import effect_catalog
from synth_effects import effect_preset, describe_effects
from synth_film_print import render_print_collage, render_film_burn
from synth_film_recipes import film_print_composition
from synth_sequence import render_sequence_frame
from synth_starters import starter_composition
from synth_studies import composition_category
from synth_video import VIDEO_EFFECTS, VIDEO_MODULES


def defaults(module):
    return {p.key:p.default for p in MODULE_BY_ID[module].params}


def source(size=(128,96)):
    w,h=size
    arr=np.zeros((h,w,3),np.float32)
    arr[h//3:2*h//3,w//4:3*w//4]=1
    arr[h//2:h//2+4,w//2:3*w//4]=.2
    return arr


@pytest.mark.parametrize('module,renderer', [('film_burn',render_film_burn),('print_collage',render_print_collage)])
def test_seek_and_cadence_are_deterministic_without_mutation(module,renderer):
    arr=source();before=arr.copy();p=defaults(module);original=copy.deepcopy(p)
    a=renderer(arr,p,1.,1.,42,(128,96))
    renderer(arr,p,8.,1.,42,(128,96))
    assert np.array_equal(a,renderer(arr,p,1.,1.,42,(128,96)))
    assert np.array_equal(a,renderer(arr,p,1.001,1.,42,(128,96)))
    assert not np.array_equal(a,renderer(arr,p,1.1,1.,42,(128,96)))
    assert np.array_equal(before,arr) and p==original
    assert np.isfinite(a).all() and 0<=a.min()<=a.max()<=1


@pytest.mark.parametrize('size',[(23,97),(128,32)])
@pytest.mark.parametrize('window',[(0,1),(.99,.01),(.5,.5)])
def test_collage_extreme_crops_and_overprints_are_bounded(size,window):
    p=dict(defaults('print_collage'),start=window[0],end=window[1],width=4.,height=5.,copies=6,
           poster=1.,poster_scale=8.,bars=1.,echo=1.)
    arr=source(size)
    a=render_print_collage(arr,p,3.,1.,42,size)
    assert a.shape==arr.shape and np.isfinite(a).all()
    assert 0<=a.min()<=a.max()<=1
    assert np.array_equal(render_print_collage(arr*0,p,3.,1.,42,size),arr*0)


def test_gate_can_close_completely_and_color_print_can_be_disabled():
    arr=source()
    p=defaults('film_burn')
    assert not np.any(render_film_burn(arr,dict(p,opening=0),0.,1.,3,(128,96)))
    base=render_film_burn(arr,p,0.,1.,3,(128,96))
    printed=render_film_burn(arr,dict(p,print_mix=1),0.,1.,3,(128,96))
    assert np.mean(abs(base-printed))>.1


@pytest.mark.parametrize('module', ['print_collage','film_burn'])
def test_new_passes_work_on_footage_and_zero_intensity_preserves_it(module):
    assert module in VIDEO_MODULES and module in VIDEO_EFFECTS
    assert module in {e.id for e in effect_catalog()}
    p=default_synth_preset()
    for m in p['modules']:m['enabled']=m['id']==module
    m=next(m for m in p['modules'] if m['id']==module)
    image=Image.fromarray(np.uint8(source()*255))
    assert render_synth_frame(p,size=image.size,source_image=image).tobytes()!=image.tobytes()
    m['params']['effect_intensity']=0
    assert render_synth_frame(p,size=image.size,source_image=image).tobytes()==image.tobytes()
    for old in curated_presets().values():
        assert not any(m['enabled'] for m in old['modules'] if m['id']==module)


def test_portable_study_and_authored_factory_match_after_save(tmp_path):
    p=starter_composition('text-film-burn')
    assert composition_category(p)=='Text'
    seq=compile_composition(p)
    assert seq['duration']==10.25 and seq['fps']==12
    assert (seq['canvas']['width'],seq['canvas']['height'])==(956,720)
    assert len(seq['cues'])==123
    save_composition(tmp_path/'print.json',p)
    restored=compile_composition(load_composition(tmp_path/'print.json'))
    authored=compile_composition(film_print_composition())
    for t in (0.,.67,2.92,4.5,6.83,9.42,10.17):
        expected=render_sequence_frame(seq,t,(160,120)).tobytes()
        assert render_sequence_frame(restored,t,(160,120)).tobytes()==expected
        assert render_sequence_frame(authored,t,(160,120)).tobytes()==expected
    # A whole-project edit replaces only the chosen control, not the montage.
    p['effects']['film_burn']=effect_preset('film_burn')
    p['effects']['film_burn']['params']={'film_burn.paper_hue':.55}
    changed=compile_composition(p)
    assert len(changed['cues'])==123
    assert render_sequence_frame(seq,3.,(160,120)).tobytes()!=render_sequence_frame(changed,3.,(160,120)).tobytes()


def test_halo_does_not_light_a_flat_gray_photograph_and_leak_hue_works():
    arr=np.full((64,96,3),.4,np.float32)
    p=dict(defaults('film_burn'),print_mix=0.,exposure=0.,grain=0.,dust=0.,
           melt=0.,softness=0.,opening=2.,roughness=0.)
    dry=render_film_burn(arr,dict(p,halo=0),0.,1.,3,(96,64))
    assert np.max(abs(render_film_burn(arr,p,0.,1.,3,(96,64))-dry))<.005
    warm=render_film_burn(arr,dict(p,exposure=.8,leak_hue=.1),0.,1.,3,(96,64))
    cool=render_film_burn(arr,dict(p,exposure=.8,leak_hue=.6),0.,1.,3,(96,64))
    assert np.mean(abs(warm-cool))>.02
