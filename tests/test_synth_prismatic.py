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


@pytest.mark.parametrize('time', [.7, 10., 13.2])
@pytest.mark.parametrize('scale', [.15,.7,3.])
def test_wider_canvas_reveals_field_without_stretching_geometry(time,scale):
    preset=resolve_sequence_frame(compile_composition(prismatic_composition()),time)[-1]
    preset.update(width=180,height=320)
    for m in preset['modules']:
        if m['id']=='film_emulsion': m['enabled']=False
        if m['id']=='prismatic_field': m['params']['size']=scale
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


def test_original_prismatic_study_regression_pixels():
    import hashlib, json
    from pathlib import Path
    # 0.18 corrects the orphan ribbon at 8s and 11.9s. The other five hashes
    # still protect the original open planes and fully gathered endpoint.
    manifest=json.loads((Path(__file__).parent/'fixtures/prismatic-film-v1-hashes.json').read_text())
    sequence=compile_composition(starter_composition('prismatic-film-original'))
    for row in manifest:
        image=render_sequence_frame(sequence,row['time'],(144,256))
        assert hashlib.sha256(image.tobytes()).hexdigest()==row['sha256']


@pytest.mark.parametrize('shape', range(7))
@pytest.mark.parametrize('scale', [.15,.7,1.,3.])
def test_ribbon_stays_inside_gathering_silhouette_at_every_shape_and_scale(monkeypatch,shape,scale):
    import synth_prismatic
    # Flat colors isolate the actual rendered coverage, independently of the
    # polygon-distance math: black background, white fold, red edge ribbon.
    def render(params):
        colors=iter(((0.,0.,0.),(1.,1.,1.),(1.,0.,0.)))
        monkeypatch.setattr(synth_prismatic,'_colors',
                            lambda coordinate,palette: np.broadcast_to(next(colors),coordinate.shape+(3,)))
        return synth_prismatic.render_prismatic_field(np.zeros((128,96,3),np.float32),params,10.,preset)
    preset=default_synth_preset();preset.update(width=96,height=128)
    params=dict(defaults('prismatic_field'),shape=shape,sides=8,size=scale,
                shading=0.,rotation=333.,rotation_speed=0.,fold_depth=0.,drift=0.)
    background_pixels=0
    for gather in (.01,.28,.65,.96,1.):
        for opening in (.01,.7,1.5):
            plain=render(dict(params,gather=gather,opening=opening,ribbon=0.))
            ribbon=render(dict(params,gather=gather,opening=opening,ribbon=1.))
            background=plain[...,0]==0.
            background_pixels+=np.count_nonzero(background)
            assert np.array_equal(ribbon[background],plain[background])
            assert np.isfinite(ribbon).all()
    assert background_pixels>0  # Large closed shapes can fill the entire view.


def test_ribbon_remains_visible_inside_fold_and_disappears_at_closed_shape():
    import synth_prismatic
    preset=default_synth_preset();preset.update(width=240,height=320)
    arr=np.zeros((320,240,3),np.float32)
    params=dict(defaults('prismatic_field'),size=.7,shape=1,gather=.65,
                opening=.74,rotation=333.58,rotation_speed=0.,fold_depth=0.,drift=0.)
    def render(ribbon,gather):
        return synth_prismatic.render_prismatic_field(arr,dict(params,ribbon=ribbon,gather=gather),10.,preset)
    assert np.max(np.abs(render(1.,.65)-render(0.,.65)))>.05
    assert np.array_equal(render(1.,1.),render(0.,1.))


@pytest.mark.parametrize('shape', range(7))
@pytest.mark.parametrize('angle', [0.,37.,360.])
def test_final_shapes_center_visible_bounds_and_follow_object_offsets(shape,angle):
    from synth_prismatic import prismatic_frame,closed_shape_field
    p=default_synth_preset();p.update(width=360,height=640,object_x=13,object_y=-7)
    params=dict(defaults('prismatic_field'),shape=shape,sides=7,gather=1.,center_shape=1,
                rotation=angle,rotation_speed=0.,drift=.8)
    yy,xx=np.mgrid[:640,:360].astype(np.float32)
    bounds=[]
    for t in (0.,4.,14.):
        (cx,cy),unit,rotation=prismatic_frame(params,(360,640),t,p)
        a=np.deg2rad(rotation);x=(xx-cx)/unit;y=(yy-cy)/unit
        field=closed_shape_field(x*np.cos(a)+y*np.sin(a),-x*np.sin(a)+y*np.cos(a),params)
        rows,columns=np.where(field>=0)
        center=((columns.min()+columns.max())/2,(rows.min()+rows.max())/2)
        assert center==pytest.approx((193.,313.),abs=1.)
        bounds.append((cx,cy))
    assert bounds[0]==bounds[1]==bounds[2]  # Final centering removes hinge drift.


def test_square_and_diamond_have_distinct_readable_orientations():
    from synth_prismatic import closed_shape_field
    square=dict(defaults('prismatic_field'),shape=2)
    diamond=dict(square,shape=3)
    assert closed_shape_field(np.array(.27),np.array(.27),square)>0
    assert closed_shape_field(np.array(.27),np.array(.27),diamond)<0
    assert closed_shape_field(np.array(0.),np.array(.36),diamond)>0
    assert closed_shape_field(np.array(0.),np.array(.36),square)<0


def test_transition_curve_has_fast_middle_soft_endpoints_and_restrained_settle():
    from synth_prismatic import transition_progress
    from synth_sequence import _ease
    values=np.linspace(0.,1.,501)
    old=np.array([_ease(t) for t in values])
    neutral=np.array([transition_progress(t,_ease(t),{},rotation=True) for t in values])
    assert np.array_equal(old,neutral)
    p=dict(transition_ease=.9,turn_settle=.6)
    motion=np.array([transition_progress(t,_ease(t),p,rotation=True) for t in values])
    assert motion[0]==0. and motion[-1]==1.
    assert motion[250]>.8 and old[250]==.5
    assert 1.01<motion.max()<1.08
    assert abs(motion[1]-motion[0])<.0001 and abs(motion[-1]-motion[-2])<.0001
    folds=np.array([transition_progress(t,_ease(t),p) for t in values])
    assert folds.min()==0. and folds.max()==1. and np.all(np.diff(folds)>=0)


def test_motion_controls_affect_authored_geometry_without_retiming_color_or_grain():
    project=prismatic_composition()
    old=copy.deepcopy(project)
    old['effects']['prismatic_field']={'mode':'recipe','params':{'prismatic_field.transition_ease':0.,'prismatic_field.turn_settle':0.}}
    new_sequence,old_sequence=compile_composition(project),compile_composition(old)
    def modules_at(s,t):
        return {m['id']:m['params'] for m in resolve_sequence_frame(s,t)[-1]['modules']}
    new,legacy=modules_at(new_sequence,4.),modules_at(old_sequence,4.)
    assert abs(new['prismatic_field']['rotation']-legacy['prismatic_field']['rotation'])>10
    for key in ('palette','color_phase','color_speed','wash'):
        assert new['prismatic_field'][key]==legacy['prismatic_field'][key]
    assert new['film_emulsion']==legacy['film_emulsion']
    for t in (0.,4.7,15.):
        assert modules_at(new_sequence,t)['prismatic_field']['rotation']==modules_at(old_sequence,t)['prismatic_field']['rotation']
