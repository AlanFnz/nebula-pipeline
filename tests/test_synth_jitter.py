import copy

import numpy as np
import pytest

from synth import MODULE_BY_ID
from synth_composition import compile_composition, ink_bloom_composition, mixed_media_composition, reference_composition
from synth_effects import effect_preset
from synth_jitter import frame_pose, render_frame_jitter
from synth_sequence import render_sequence_frame


def params(**changes):
    return {**{p.key: p.default for p in MODULE_BY_ID['frame_jitter'].params}, **changes}


def test_registration_has_an_independent_held_clock_and_random_access():
    p = params()
    a = frame_pose(p, .001, 1, 27)
    assert a == frame_pose(p, .05, 1, 27)
    assert a != frame_pose(p, .07, 1, 27)
    frame_pose(p, 1_000_000, 1, 27)
    assert a == frame_pose(p, .001, 1, 27)
    assert frame_pose(p, 0, 0, 27) == frame_pose(p, 100, 0, 27)
    assert frame_pose(dict(p, rate=0), 0, 1, 27) == frame_pose(dict(p, rate=0), 100, 1, 27)
    assert a != frame_pose(dict(p, seed=1), .001, 1, 27)
    assert frame_pose(p, .07, 2, 27) == frame_pose(p, .14, 1, 27)


def test_jitter_is_bounded_around_the_authored_position_without_accumulating_drift():
    p = params()
    poses = np.array([frame_pose(p, i / 15, 1, 9) for i in range(300)])
    limits = np.array((p['x'], p['y'], p['rotation'], p['scale'] / 100))
    poses[:, 3] -= 1
    assert np.all(np.abs(poses) <= limits)
    assert np.all(np.abs(poses.mean(0)) < limits * .1)
    assert np.all(poses.std(0) > limits * .4)


def centroid(arr):
    weights = arr.sum(2)
    y, x = np.mgrid[:arr.shape[0], :arr.shape[1]]
    return np.array(((weights * x).sum(), (weights * y).sum())) / weights.sum()


def test_source_translates_by_the_pose_at_subpixel_precision_without_clipping_highlights():
    p = params(rotation=0., scale=0.)
    source = np.zeros((144, 180, 3), np.float32); source[54:90, 70:110] = (3., .5, 1.)
    before = source.copy()
    result = render_frame_jitter(source, p, .4, 1, 11)
    pose = np.array(frame_pose(p, .4, 1, 11)[:2]) * 144 / 720
    assert np.allclose(centroid(result) - centroid(source), pose, atol=.0001)
    assert result.max() == 3.
    assert np.array_equal(source, before)
    # Scaling the canvas scales the same registration displacement.
    large = np.repeat(np.repeat(source, 2, axis=0), 2, axis=1)
    shifted = render_frame_jitter(large, p, .4, 1, 11)
    assert np.allclose(centroid(shifted) - centroid(large), pose * 2, atol=.0001)


def test_bypass_edges_rotation_and_scale():
    source = np.zeros((100, 160, 3), np.float32); source[:, :12] = 2.; source[30:70, 60:100] = 1.
    p = params()
    assert render_frame_jitter(source, dict(p, strength=0), .4, 1, 4) is source
    assert render_frame_jitter(source, dict(p, x=0, y=0, rotation=0, scale=0), .4, 1, 4) is source
    for time in (0., .4, 20., 1_000_000.):
        moved = render_frame_jitter(source, params(x=30., y=30., rotation=3., scale=3., strength=2.), time, 1, 4)
        assert np.isfinite(moved).all()
        assert not moved[:, -20:].any()  # The left-edge strip never wraps right.
    flat = np.full_like(source, .17)
    assert np.allclose(render_frame_jitter(flat, p, .4, 1, 4), flat)
    center = np.zeros_like(source); center[25:75, 65:95] = 1.
    for changed in (params(x=0, y=0, rotation=3., scale=0), params(x=0, y=0, rotation=0, scale=3.)):
        assert not np.array_equal(center, render_frame_jitter(center, changed, .4, 1, 4))


def test_effect_moves_the_figure_independently_of_the_print_background():
    project = ink_bloom_composition()
    a = np.asarray(render_sequence_frame(compile_composition(project), 1.6, (240, 240)))
    before = copy.deepcopy(project['source'])
    project['effects']['frame_jitter'] = effect_preset('frame_jitter')
    b = np.asarray(render_sequence_frame(compile_composition(project), 1.6, (240, 240)))
    assert np.array_equal(a[:20, :20], b[:20, :20])
    assert not np.array_equal(a[60:180, 60:180], b[60:180, 60:180])
    assert project['source'] == before
    project['effects']['frame_jitter']['params']['frame_jitter.strength'] = 0
    assert np.array_equal(a, render_sequence_frame(compile_composition(project), 1.6, (240, 240)))
    # It is a reusable source treatment and does not require Ink bloom or Print surface.
    signal = reference_composition()
    a = render_sequence_frame(compile_composition(signal), 1.6, (160, 128)).tobytes()
    signal['effects']['frame_jitter'] = effect_preset('frame_jitter')
    assert a != render_sequence_frame(compile_composition(signal), 1.6, (160, 128)).tobytes()


def test_mixed_media_starter_embeds_two_distinct_gestures_and_independent_settings():
    project = mixed_media_composition(); second = mixed_media_composition()
    assert len(project['sections']) == 2
    sequence = compile_composition(project)
    assert sequence['duration'] == pytest.approx(106 / 15)
    assert sequence['fps'] == 15 and len(sequence['cues']) == 2
    settings = [s['overrides'] for s in sequence['states'].values()]
    assert [s['ink_bloom.revolutions'] for s in settings] == [1., -1.]
    assert settings[1]['ink_bloom.spread'] > settings[0]['ink_bloom.spread']
    assert all('frame_jitter' in s['enabled'] for s in sequence['states'].values())
    assert all(s['frame_jitter.rate'] == 15 for s in settings)
    project['source']['states']['first']['overrides']['frame_jitter.x'] = 20.
    assert second['source']['states']['first']['overrides']['frame_jitter.x'] == 5.
