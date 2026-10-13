"""Prismatic source and independent emulsion preserve editable, seekable output."""
import copy

import numpy as np
import pytest
from PIL import Image

from synth import MODULE_BY_ID, curated_presets, default_synth_preset, render_synth_frame
from synth_canvas import resize_canvas
from synth_composition import compile_composition, load_composition, save_composition
from synth_effects import describe_effects
from synth_prismatic import render_film_emulsion
from synth_prismatic_recipes import prismatic_composition
from synth_sequence import render_sequence_frame, resolve_sequence_frame
from synth_source_adapters import ANCHORS, source_frame
from synth_starters import starter_composition
from synth_subject import active_subjects, scope_states, select_subject
from synth_video import VIDEO_EFFECTS


def defaults(module):
    return {spec.key: spec.default for spec in MODULE_BY_ID[module].params}


def test_study_roundtrip_preserves_motion_and_seek_pixels(tmp_path):
    project = starter_composition('prismatic-film')
    assert active_subjects(describe_effects(scope_states(project))) == ('prismatic',)
    sequence = compile_composition(project)
    assert sequence['duration'] == 15. and sequence['fps'] == 25
    assert sequence['canvas']['width'] == 720 and sequence['canvas']['height'] == 1280
    before = render_sequence_frame(sequence, 1.3, (144,256)).tobytes()
    assert before != render_sequence_frame(sequence, 8.3, (144,256)).tobytes()
    assert before == render_sequence_frame(sequence, 1.3, (144,256)).tobytes()
    path = tmp_path/'planes.json'; save_composition(path,project)
    assert before == render_sequence_frame(compile_composition(load_composition(path)),1.3,(144,256)).tobytes()
    # Published Study is a frozen copy, with every authored parameter explicit.
    assert project == prismatic_composition()


@pytest.mark.parametrize('time', [.7, 13.2])
def test_wider_canvas_reveals_field_without_stretching_geometry(time):
    preset=resolve_sequence_frame(compile_composition(prismatic_composition()),time)[-1]
    preset.update(width=180,height=320)
    for m in preset['modules']:
        if m['id']=='film_emulsion': m['enabled']=False
    original=np.asarray(render_synth_frame(preset,time_seconds=time))
    wider=copy.deepcopy(preset)
    wider.update(resize_canvas(preset,dict(width=300,height=320)))
    rendered=np.asarray(render_synth_frame(wider,time_seconds=time))
    assert np.array_equal(original,rendered[:,60:240])
    assert rendered[:,:60].std()>8 and rendered[:,-60:].std()>8


def test_anchor_tracks_source_and_keeps_existing_anchor_numbers():
    assert ANCHORS[:8] == ('auto','silhouette','slab','ink_bloom','particles','blinds','text','radial_bloom')
    p=resolve_sequence_frame(compile_composition(prismatic_composition()),.7)[-1]
    automatic=source_frame(p,(180,320),0.,continuous_time=2.)
    assert automatic==source_frame(p,(180,320),2.,'prismatic_field')
    moved=source_frame(dict(p,object_x=p['object_x']+40,object_y=p['object_y']-20),(180,320),2.)
    assert np.subtract(moved.origin,automatic.origin)==pytest.approx((10.,-5.))


def test_old_presets_opt_out_and_switch_keeps_existing_treatments():
    for p in curated_presets().values():
        assert not any(m['enabled'] for m in p['modules'] if m['id'] in ('prismatic_field','film_emulsion'))
    old=starter_composition('text-night')
    changed=select_subject(old,'prismatic')
    summary=describe_effects(scope_states(changed))
    assert active_subjects(summary)==('prismatic',)
    assert summary['bloom']['active']
    assert changed['sections']==old['sections']


def test_emulsion_neutral_hold_and_seek_with_no_black_exposed_edges():
    arr=np.full((80,100,3),.45,np.float32)
    p=defaults('film_emulsion')
    assert render_film_emulsion(arr,dict(p,mix=0),1.,1.,3,(100,80)) is arr
    plain=render_film_emulsion(arr,dict(p,grain=0,flicker=0,registration=12),1.,1.,3,(100,80))
    assert plain.min()>.4  # Shifted channels extend existing edge pixels.
    a=render_film_emulsion(arr,p,1.,1.,3,(100,80))
    assert np.array_equal(a,render_film_emulsion(arr,p,1.001,1.,3,(100,80))) is False # Flutter stays continuous.
    held=dict(p,flicker=0)
    assert np.array_equal(render_film_emulsion(arr,held,1.,1.,3,(100,80)),
                          render_film_emulsion(arr,held,1.001,1.,3,(100,80)))
    assert not np.array_equal(a,render_film_emulsion(arr,p,1.04,1.,3,(100,80)))
    assert np.array_equal(a,render_film_emulsion(arr,p,1.,1.,3,(100,80)))
    assert np.array_equal(arr,np.full_like(arr,.45))


def test_emulsion_applies_to_imported_pixels_without_a_generated_source():
    assert 'film_emulsion' in VIDEO_EFFECTS
    p=default_synth_preset();p.update(width=96,height=96)
    for m in p['modules']: m['enabled']=False
    source=Image.fromarray(np.tile(np.arange(96,dtype=np.uint8)[None,:,None]*2,(96,1,3)))
    before=render_synth_frame(p,source_image=source)
    next(m for m in p['modules'] if m['id']=='film_emulsion')['enabled']=True
    after=render_synth_frame(p,source_image=source)
    assert after.tobytes()!=before.tobytes()
    assert after.size==source.size


@pytest.mark.parametrize('sides', [3,4,8])
@pytest.mark.parametrize('gather', [0.,.5,1.])
def test_shape_variants_render_finite_filled_frames(sides,gather):
    from synth_prismatic import render_prismatic_field
    p=default_synth_preset();p.update(width=80,height=128)
    params=dict(defaults('prismatic_field'),sides=sides,gather=gather)
    result=render_prismatic_field(np.zeros((128,80,3),np.float32),params,3.6,p)
    assert result.shape==(128,80,3) and np.isfinite(result).all()
    assert result.std()>.05 and result.min()>0
