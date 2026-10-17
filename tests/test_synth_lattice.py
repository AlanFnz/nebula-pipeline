import copy

import numpy as np
import pytest

from synth import MODULE_BY_ID, curated_presets, default_synth_preset, render_synth_frame
from synth_canvas import resize_canvas
from synth_composition import compile_composition, load_composition, save_composition
from synth_effect_catalog import effect_catalog
from synth_effects import describe_effects
from synth_lattice import render_chromatic_lattice, pulse_size
from synth_lattice_recipes import lattice_composition
from synth_sequence import render_sequence_frame, resolve_sequence_frame
from synth_source_adapters import source_frame
from synth_starters import starter_composition
from synth_studies import composition_category
from synth_subject import active_subjects, scope_states, select_subject


def defaults():
    return {p.key:p.default for p in MODULE_BY_ID['chromatic_lattice'].params}


def test_portable_study_roundtrip_and_random_seek(tmp_path):
    p=starter_composition('chromatic-lattice')
    assert p==lattice_composition()
    assert composition_category(p)=='Signals'
    assert active_subjects(describe_effects(scope_states(p)))==('lattice',)
    assert 'chromatic_lattice' not in {e.id for e in effect_catalog()}
    seq=compile_composition(p)
    assert seq['duration']==20. and seq['fps']==30
    assert (seq['canvas']['width'],seq['canvas']['height'])==(720,1280)
    a=render_sequence_frame(seq,1.7,(144,256)).tobytes()
    assert a!=render_sequence_frame(seq,3.1,(144,256)).tobytes()
    assert a==render_sequence_frame(seq,1.7,(144,256)).tobytes()
    save_composition(tmp_path/'lattice.json',p)
    assert a==render_sequence_frame(compile_composition(load_composition(tmp_path/'lattice.json')),1.7,(144,256)).tobytes()
    empty=select_subject(p,'none')
    assert active_subjects(describe_effects(scope_states(empty)))==()
    assert active_subjects(describe_effects(scope_states(select_subject(empty,'text'))))==('text',)


@pytest.mark.parametrize('shape,sides',[(0,6),(1,6),(2,6),(3,3),(3,5),(3,12)])
@pytest.mark.parametrize('wave', [0,1,2])
def test_shape_wave_extremes_are_finite_and_never_mutate_input(shape,sides,wave):
    arr=np.full((97,131,3),.2,np.float32)
    preset=dict(default_synth_preset(),width=131,height=97)
    p=dict(defaults(),shape=shape,sides=sides,wave_shape=wave,spacing=24.,rotation=45.,size=1.)
    for t in (0.,2.5,19.99):
        result=render_chromatic_lattice(arr,p,t,preset)
        assert result.shape==arr.shape and np.isfinite(result).all()
        assert result.min()>=0 and result.max()<=1
    assert np.all(arr==np.float32(.2))
    assert render_chromatic_lattice(arr,dict(p,mix=0),1.,preset) is arr


def test_pulses_repeat_and_reversing_direction_reverses_travel():
    p=defaults();d=np.array((0.,1.,3.,8.,13.))
    assert pulse_size(d,0,p)==pytest.approx(pulse_size(d,p['period'],p))
    assert pulse_size(d,1.3,p)==pytest.approx(pulse_size(d,-1.3,dict(p,direction=1)))
    assert np.all(pulse_size(d,2.,dict(p,pulse=0))==1)
    assert pulse_size(np.array((0.,)),0,p)[0]==0
    assert pulse_size(np.array((0.,)),0,dict(p,minimum=.2))[0]==pytest.approx(.2)


def test_complete_optical_cycle_has_no_color_or_size_cut():
    arr=np.zeros((128,72,3),np.float32)
    preset=dict(default_synth_preset(),width=72,height=128,speed=1.)
    p=dict(defaults(),grain=0)
    a=render_chromatic_lattice(arr,p,0,preset)
    assert np.max(np.abs(a-render_chromatic_lattice(arr,p,10,preset)))<1e-4
    assert np.mean(np.abs(a-render_chromatic_lattice(arr,p,10-1/300,preset)))<.003


def test_palettes_shapes_and_independent_controls_change_the_result():
    arr=np.zeros((192,108,3),np.float32)
    preset=dict(default_synth_preset(),width=108,height=192)
    p=defaults();a=render_chromatic_lattice(arr,p,1.,preset)
    for change in (dict(shape=1),dict(shape=2),dict(shape=3,sides=5),dict(palette=1),dict(palette=2),dict(palette=3),dict(period=2.),dict(color_period=4.),dict(spacing=120.),dict(glow=0),dict(gradient=0)):
        assert np.mean(np.abs(a-render_chromatic_lattice(arr,dict(p,**change),1.,preset)))>.003
    frozen=dict(preset,speed=0)
    assert np.array_equal(render_chromatic_lattice(arr,p,0.,frozen),render_chromatic_lattice(arr,p,19.,frozen))


def test_reframing_preserves_cell_proportions_and_anchor():
    preset=resolve_sequence_frame(compile_composition(lattice_composition()),0)[-1]
    preset.update(width=180,height=320)
    module=next(m for m in preset['modules'] if m['id']=='chromatic_lattice')
    module['params'].update(grain=0,softness=0,glow=0)
    a=np.asarray(render_synth_frame(preset,time_seconds=2.))
    wide=copy.deepcopy(preset);wide.update(resize_canvas(preset,dict(width=300,height=320)))
    b=np.asarray(render_synth_frame(wide,time_seconds=2.))
    assert np.array_equal(a,b[:,60:240])
    assert source_frame(preset,(180,320),0).origin==(90.,160.)
    assert source_frame(dict(preset,object_x=40,object_y=-20),(180,320),0).origin==pytest.approx((130.,140.))


def test_new_source_is_disabled_in_all_existing_curated_presets():
    for preset in curated_presets().values():
        assert not next(m for m in preset['modules'] if m['id']=='chromatic_lattice')['enabled']
