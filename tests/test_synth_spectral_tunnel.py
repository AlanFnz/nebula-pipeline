import copy

import numpy as np
import pytest

from synth import MODULE_BY_ID, curated_presets, default_synth_preset
from synth_composition import compile_composition, load_composition, save_composition
from synth_effect_catalog import effect_catalog
from synth_effects import describe_effects
from synth_sequence import render_sequence_frame
from synth_spectral_tunnel import loop_phase, render_spectral_tunnel
from synth_spectral_tunnel_recipes import spectral_tunnel_composition
from synth_starters import starter_composition
from synth_studies import composition_category
from synth_subject import active_subjects, scope_states, select_subject


def defaults():
    return {p.key: p.default for p in MODULE_BY_ID['spectral_tunnel'].params}


def test_portable_study_and_subject_switching(tmp_path):
    project = starter_composition('spectral-tunnel')
    assert project == spectral_tunnel_composition()
    assert composition_category(project) == 'Signals'
    assert active_subjects(describe_effects(scope_states(project))) == ('tunnel',)
    assert 'spectral_tunnel' not in {e.id for e in effect_catalog()}
    seq = compile_composition(project)
    assert seq['duration'] == 6. and seq['fps'] == 100
    assert (seq['canvas']['width'], seq['canvas']['height']) == (500, 500)
    frame = render_sequence_frame(seq, .09, (128, 128)).tobytes()
    assert frame != render_sequence_frame(seq, .21, (128, 128)).tobytes()
    save_composition(tmp_path/'loop.json', project)
    restored = compile_composition(load_composition(tmp_path/'loop.json'))
    assert frame == render_sequence_frame(restored, .09, (128, 128)).tobytes()
    empty = select_subject(project, 'none')
    assert active_subjects(describe_effects(scope_states(empty))) == ()
    assert active_subjects(describe_effects(scope_states(select_subject(empty, 'tunnel')))) == ('tunnel',)


@pytest.mark.parametrize('motion', [0, 1])
def test_cycle_including_grain_is_exact_and_random_access(motion):
    p = dict(defaults(), motion=motion)
    arr = np.zeros((96, 96, 3), np.float32)
    preset = dict(default_synth_preset(), width=96, height=96)
    for t in (0., .03, .09, .27):
        a = render_spectral_tunnel(arr, p, t, preset)
        render_spectral_tunnel(arr, p, .21, preset)
        assert np.array_equal(a, render_spectral_tunnel(arr, p, t+6., preset))
    assert loop_phase(.3, p) == loop_phase(0., p)
    assert loop_phase(.029, p) == 0.
    assert loop_phase(.03, p) == .1
    assert loop_phase(.3, p, 0.) == 0.


@pytest.mark.parametrize('shape', [0, 1, 2, 3])
def test_shapes_and_extreme_geometry_are_bounded(shape):
    arr = np.full((73, 97, 3), .2, np.float32)
    preset = dict(default_synth_preset(), width=97, height=73)
    p = dict(defaults(), shape=shape, rows=60, spacing=8., vanishing_x=.65,
             cross_x=.8, size=2., aspect=1.5, spread=2., sides=3)
    out = render_spectral_tunnel(arr, p, .15, preset)
    assert out.shape == arr.shape and np.isfinite(out).all()
    assert 0 <= out.min() <= out.max() <= 1
    assert np.all(arr == np.float32(.2))
    assert render_spectral_tunnel(arr, dict(p, mix=0.), .15, preset) is arr


def test_control_changes_and_continuous_seam():
    p = dict(defaults(), grain=0., cadence=0)
    arr = np.zeros((160, 160, 3), np.float32)
    preset = dict(default_synth_preset(), width=160, height=160, speed=1.)
    base = render_spectral_tunnel(arr, p, 0., preset)
    end = render_spectral_tunnel(arr, p, .3-1e-5, preset)
    assert np.mean(np.abs(end-base)) < .001
    for change in (dict(rail=0), dict(glow=0), dict(warm_hue=.4), dict(horizon=.4), dict(size=.6)):
        out = render_spectral_tunnel(arr, dict(p, **change), 0., preset)
        assert np.mean(np.abs(out-base)) > .005


def test_does_not_enable_itself_in_existing_presets():
    for preset in curated_presets().values():
        before = copy.deepcopy(preset)
        assert not next(m for m in preset['modules'] if m['id']=='spectral_tunnel')['enabled']
        assert preset == before
