import copy
import hashlib

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
    assert project['source']['states']['ripple']['overrides']['spectral_tunnel.motion'] == 1
    assert seq['duration'] == 6. and seq['fps'] == 50
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


def test_original_ripple_render_is_unchanged():
    arr = np.zeros((96, 96, 3), np.float32)
    preset = dict(default_synth_preset(), width=96, height=96, speed=1., seed=151026)
    image = render_spectral_tunnel(arr, defaults(), .09, preset)
    # Captured from 0.88.0 before correcting the reference study.
    assert hashlib.sha256(np.uint8(image*255).tobytes()).hexdigest() == (
        '0a73c3806907236023286f6ca437c92e1a74d07ce1e987e1c23e235abc4ee81d')


@pytest.mark.parametrize('shape', [0, 1, 2, 3])
def test_left_orientation_reprojects_geometry_and_keeps_background(shape):
    arr = np.zeros((96, 128, 3), np.float32)
    arr[:, :40, 0] = .7  # An asymmetric underlying image must not move.
    preset = dict(default_synth_preset(), width=128, height=96)
    p = dict(defaults(), shape=shape, sides=3, grain=0., softness=0., mix=.6)
    right = render_spectral_tunnel(arr, p, .09, preset) - arr * .4
    left = render_spectral_tunnel(arr, dict(p, orientation=1), .09, preset) - arr * .4
    # Reflection around the object's geometric center (x=64), not the pixel
    # array's center (x=63.5). Compare matching interior sample coordinates.
    assert np.mean(np.abs(left[:, 1:] - right[:, :0:-1])) < .0001
    assert not np.allclose(left, right)
    assert np.array_equal(left, render_spectral_tunnel(arr, dict(p, orientation=1), 6.09, preset) - arr * .4)


def test_a_light_moves_continuously_toward_the_foreground():
    from synth_sequence import resolve_sequence_frame
    seq = compile_composition(spectral_tunnel_composition())
    preset = resolve_sequence_frame(seq, 0.)[-1]
    p = next(m['params'] for m in preset['modules'] if m['id']=='spectral_tunnel')
    p = dict(p, grain=0.)
    preset.update(width=320, height=320)
    previous, trace = 205., []
    for frame in range(10):
        image = render_spectral_tunnel(np.zeros((320,320,3),np.float32), p, frame*p['period']/10, preset)
        mask = image.min(2) > .84
        seen = np.zeros(mask.shape, bool)
        candidates = []
        # Track a connected emitter, not a centroid containing multiple lights.
        for y, x in zip(*np.where(mask)):
            if seen[y,x]:
                continue
            pending = [(y,x)]; seen[y,x] = True
            sx = sy = count = 0
            while pending:
                yy, xx = pending.pop(); sx += xx; sy += yy; count += 1
                for ry, rx in ((yy-1,xx),(yy+1,xx),(yy,xx-1),(yy,xx+1)):
                    if 0 <= rx < 320 and 0 <= ry < 320 and mask[ry,rx] and not seen[ry,rx]:
                        seen[ry,rx] = True; pending.append((ry,rx))
            cx, cy = sx/count/.64, sy/count/.64
            if count > 10 and 120 < cx < 250 and abs(cy-(29+.403*cx)) < 5:
                candidates.append(cx)
        previous = min(candidates, key=lambda x: abs(x-previous))
        trace.append(previous)
    # Positions measured in the supplied GIF, in its original 500px coordinates.
    reference = np.array([205.,201.4,197.6,193.9,190.,186.3,182.5,178.4,174.3,170.1])
    assert np.all(np.diff(trace) < -2.)
    assert np.max(np.abs(np.array(trace)-reference)) < 2.
