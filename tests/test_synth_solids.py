import copy

import numpy as np
import pytest

from synth import MODULE_BY_ID, curated_presets, default_synth_preset, render_synth_frame
from synth_canvas import resize_canvas
from synth_composition import compile_composition, load_composition, save_composition
from synth_effects import describe_effects
from synth_effect_catalog import effect_catalog
from synth_sequence import render_sequence_frame, resolve_sequence_frame
from synth_solid_recipes import rotating_die_composition
from synth_solids import render_color_field, render_solid
from synth_source_adapters import ANCHORS, source_frame
from synth_starters import starter_composition
from synth_subject import active_subjects, scope_states, select_subject


def defaults(module):
    return {spec.key: spec.default for spec in MODULE_BY_ID[module].params}


def test_study_roundtrip_and_seeking_are_deterministic(tmp_path):
    project = starter_composition('color-film-die')
    assert project == rotating_die_composition()
    summary = describe_effects(scope_states(project))
    assert active_subjects(summary) == ('solid',)
    assert summary['color_field']['active'] and summary['film_emulsion']['active']
    seq = compile_composition(project)
    assert seq['duration'] == 15. and seq['fps'] == 25
    assert (seq['canvas']['width'], seq['canvas']['height']) == (720,1280)
    a = render_sequence_frame(seq, 1.3, (144,256)).tobytes()
    assert a != render_sequence_frame(seq, 7.1, (144,256)).tobytes()
    assert a == render_sequence_frame(seq, 1.3, (144,256)).tobytes()
    save_composition(tmp_path/'die.json',project)
    assert a == render_sequence_frame(compile_composition(load_composition(tmp_path/'die.json')),1.3,(144,256)).tobytes()


@pytest.mark.parametrize('yaw,pitch,count', [(0,0,3),(180,0,4),(-90,0,1),(90,0,6),(0,90,2),(0,-90,5)])
def test_rendered_face_has_the_correct_number_of_attached_dots(yaw,pitch,count):
    arr = np.zeros((240,240,3),np.float32)
    preset = dict(default_synth_preset(),width=240,height=240)
    p = dict(defaults('solid'),scale=.7,yaw=yaw,pitch=pitch,roll=0,
             turn_speed=0,tumble_speed=0,roll_speed=0,perspective=0,pip_light=0)
    die = render_solid(arr,p,2.,preset)
    cube = render_solid(arr,dict(p,shape=1),2.,preset)
    remaining = set(zip(*np.nonzero(np.max(cube-die,axis=-1)>.1)))
    components = 0
    while remaining:
        stack = [remaining.pop()]; components += 1
        while stack:
            y,x = stack.pop()
            for neighbor in ((y-1,x),(y+1,x),(y,x-1),(y,x+1)):
                if neighbor in remaining:
                    remaining.remove(neighbor); stack.append(neighbor)
    assert components == count


def test_background_and_no_object_are_independent_of_solid_controls():
    p = rotating_die_composition()
    background = select_subject(p,'none')
    summary = describe_effects(scope_states(background))
    assert active_subjects(summary) == ()
    assert summary['color_field']['active'] and summary['film_emulsion']['active']
    changed = select_subject(background,'text')
    assert describe_effects(scope_states(changed))['color_field']['active']
    catalog = {e.id for e in effect_catalog()}
    assert 'color_field' in catalog and 'solid' not in catalog
    preset = dict(default_synth_preset(),width=180,height=320)
    arr = np.zeros((320,180,3),np.float32)
    field = render_color_field(arr,defaults('color_field'),2.,preset)
    assert np.array_equal(field,render_color_field(arr,defaults('color_field'),2.,dict(preset,object_x=100,object_y=-80)))
    assert field.std()>.05


@pytest.mark.parametrize('time', [0.,4.3,14.96])
def test_canvas_resize_reveals_more_background_without_stretching_die(time):
    preset = resolve_sequence_frame(compile_composition(rotating_die_composition()),time)[-1]
    preset.update(width=180,height=320)
    for m in preset['modules']:
        if m['id'] in ('film_emulsion','broadcast'): m['enabled']=False
    a = np.asarray(render_synth_frame(preset,time_seconds=time))
    wide = copy.deepcopy(preset)
    wide.update(resize_canvas(preset,dict(width=300,height=320)))
    b = np.asarray(render_synth_frame(wide,time_seconds=time))
    assert np.array_equal(a,b[:,60:240])
    assert b[:,:60].std()>8


def test_anchor_tracks_offset_and_solid_stays_centered():
    assert ANCHORS[:9] == ('auto','silhouette','slab','ink_bloom','particles','blinds','text','radial_bloom','prismatic_field')
    preset = resolve_sequence_frame(compile_composition(rotating_die_composition()),0.)[-1]
    for t in (0.,3.2,8.7,14.96):
        frame = source_frame(preset,(180,320),0.,continuous_time=t)
        assert frame.origin == (90.,160.)
        assert frame == source_frame(preset,(180,320),t,'solid')
    moved = source_frame(dict(preset,object_x=40,object_y=-20),(180,320),0.)
    assert np.subtract(moved.origin,(90,160)) == pytest.approx((10,-5))


@pytest.mark.parametrize('scale,perspective', [(.05,0),(.05,1),(2,0),(2,1)])
def test_extreme_sizes_and_projection_remain_finite(scale,perspective):
    arr = np.full((73,127,3),.2,np.float32)
    preset = dict(default_synth_preset(),width=127,height=73)
    p = dict(defaults('solid'),scale=scale,perspective=perspective)
    for t in (0.,1.7,9.):
        result = render_solid(arr,p,t,preset)
        assert np.isfinite(result).all() and result.shape==arr.shape
    assert render_solid(arr,dict(p,mix=0),0.,preset) is arr
    assert render_color_field(arr,dict(defaults('color_field'),mix=0),0.,preset) is arr
    assert np.array_equal(arr,np.full_like(arr,.2))


def test_existing_presets_opt_out():
    for p in curated_presets().values():
        assert not any(m['enabled'] for m in p['modules'] if m['id'] in ('color_field','solid'))
