import copy

import numpy as np
import pytest

from synth import MODULE_BY_ID, default_synth_preset
from synth_composition import compile_composition, mixed_media_composition
from synth_effects import describe_effects
from synth_ink_timing import DURATION_KEYS, gesture_phase, stage_durations
from synth_print import bloom_phase, render_ink_bloom
from synth_sequence import _interpolate_presets, render_sequence_frame


def params(**changes):
    return {**{spec.key: spec.default for spec in MODULE_BY_ID['ink_bloom'].params}, **changes}


def timed_params(**changes):
    return params(period=10., open_start=10., open_duration=20., close_start=60., close_duration=20.,
                  cadence=40, unfold_seconds=1., unfolded_seconds=2., fold_seconds=.5, folded_seconds=1.5, **changes)


def test_four_stages_have_independent_durations_and_eased_motion():
    p = timed_params()
    # Five-second loop: .5s closed lead, 1s unfold, 2s open, .5s fold, 1s closed tail.
    for time, opening in ((0, 0), (.5, 0), (.75, .15625), (1., .5), (1.5, 1),
                          (2.5, 1), (3.5, 1), (3.75, .5), (4., 0), (4.9, 0), (5., 0)):
        assert bloom_phase(time, p)[2] == pytest.approx(opening)
    assert bloom_phase(1., p)[1] == pytest.approx(.2)  # Authored turn halfway through unfolding.
    assert bloom_phase(2.5, p)[1] == pytest.approx(.45)
    for key in DURATION_KEYS:
        changed = stage_durations(dict(p, **{key: p[key] + 1.}))
        assert changed[key] == p[key] + 1.
        assert all(changed[other] == p[other] for other in DURATION_KEYS if other != key)


def test_gesture_speed_cadence_freeze_manual_opening_and_repeat():
    p = timed_params()
    for time in (0., .025, .75, 1.25, 2.5, 3.75, 1000000.25):
        assert bloom_phase(time, dict(p, motion_speed=2.)) == bloom_phase(time * 2, p)
        assert bloom_phase(time, dict(p, motion_speed=2., clock_mode=1, clock_scale=.5)) == bloom_phase(time, p)
        assert bloom_phase(time, dict(p, motion_speed=0)) == bloom_phase(0, p)
    assert bloom_phase(.001, p) == bloom_phase(.024, p)
    assert bloom_phase(.75, p)[1:] == pytest.approx(bloom_phase(5.75, p)[1:])
    assert bloom_phase(.75, dict(p, cycle=0, opening=.37))[2] == .37
    source = np.zeros((120, 120, 3), np.float32)
    assert np.array_equal(render_ink_bloom(source, p, .75, 1, 4), render_ink_bloom(source, p, 5.75, 1, 4))


@pytest.mark.parametrize('motion_speed', [.05, .1, .25, .5, 1., 2.])
@pytest.mark.parametrize('clock_mode', [0, 1])
def test_gesture_speed_preserves_motion_fps_and_makes_smaller_steps(motion_speed, clock_mode):
    p = params(cadence=15, motion_speed=motion_speed, clock_mode=clock_mode)
    # Sample at 60 export fps: every motion sample spans four output frames,
    # even at 0.05x. Speed changes the distance between poses, not their rate.
    clocks = [gesture_phase(frame / 60, p)[0] for frame in range(61)]
    changes = [frame for frame in range(1, len(clocks)) if clocks[frame] != clocks[frame - 1]]
    assert changes == list(range(4, 61, 4))
    assert np.diff([clocks[0], *(clocks[frame] for frame in changes)]) == pytest.approx([motion_speed / 15] * 15)


def test_independent_clock_scale_and_long_seeks_keep_the_selected_cadence():
    p = timed_params(clock_mode=1, clock_scale=.4, motion_speed=.25)
    # Both speed multipliers are applied after the real-time hold clock.
    for time in (.013, .063, 10.013, 1000000.013):
        first = gesture_phase(time, p, speed=3.)
        assert first == gesture_phase(time + .001, p, speed=.2)
        next_frame = gesture_phase(time + 1 / p['cadence'], p)
        assert next_frame[0] - first[0] == pytest.approx(.4 * .25 / p['cadence'])
    assert gesture_phase(1000000., dict(p, motion_speed=0.))[0] == 0.


def test_slow_gesture_renders_new_poses_at_the_selected_motion_fps():
    p = params(clock_mode=1, motion_speed=.1, cadence=15)
    source = np.zeros((240, 240, 3), np.float32)
    frames = [render_ink_bloom(source, p, 6. + frame / 30, 1., 7) for frame in range(30)]
    # Fifteen distinct poses per second, with each held for two 30 fps frames.
    assert len({frame.tobytes() for frame in frames}) == 15
    assert all(np.array_equal(frames[i], frames[i + 1]) for i in range(0, 30, 2))


@pytest.mark.parametrize('durations', [dict.fromkeys(DURATION_KEYS, 0.),
                                     dict(unfold_seconds=0., unfolded_seconds=1., fold_seconds=0., folded_seconds=1.),
                                     dict(unfold_seconds=.3, unfolded_seconds=0., fold_seconds=.4, folded_seconds=0.)])
def test_instant_stages_and_zero_holds_are_finite(durations):
    p = params(**durations)
    values = [bloom_phase(time, p) for time in np.linspace(0, 10, 251)]
    assert np.isfinite(values).all()
    assert all(0 <= opening <= 1 for _, _, opening in values)
    if not any(durations.values()): assert all(opening == 0 for _, _, opening in values)


def test_one_global_duration_consolidates_the_complete_timing_profile():
    project = mixed_media_composition()
    original = copy.deepcopy(project['source'])
    before = describe_effects(compile_composition(project)['states'].values())['ink_bloom']['ranges']
    assert before['ink_bloom.unfold_seconds'] == pytest.approx((53 / 15 * .24, 53 / 15 * .28))
    assert before['ink_bloom.fold_seconds'] == pytest.approx((53 / 15 * .26, 53 / 15 * .27))
    project['effects']['ink_bloom'] = {'mode': 'recipe', 'params': {'ink_bloom.unfold_seconds': .4}}
    after = describe_effects(compile_composition(project)['states'].values())['ink_bloom']['ranges']
    assert after['ink_bloom.unfold_seconds'] == (.4, .4)
    for key in DURATION_KEYS:
        low, high = after[f'ink_bloom.{key}']
        assert low == high
    assert after['ink_bloom.fold_seconds'][0] == pytest.approx(53 / 15 * .27)
    assert project['source'] == original


def test_morphs_resolve_recipe_durations_before_interpolating():
    first = default_synth_preset(); second = copy.deepcopy(first)
    first_ink = next(m['params'] for m in first['modules'] if m['id'] == 'ink_bloom')
    second_ink = next(m['params'] for m in second['modules'] if m['id'] == 'ink_bloom')
    second_ink['unfold_seconds'] = .2
    recipe = stage_durations(first_ink)['unfold_seconds']
    for amount in (0., .2, .5, 1.):
        middle = _interpolate_presets(first, second, amount)
        ink = next(m['params'] for m in middle['modules'] if m['id'] == 'ink_bloom')
        assert ink['unfold_seconds'] == pytest.approx(recipe * (1 - amount) + .2 * amount)
        assert all(ink[key] == -1 for key in DURATION_KEYS[1:])
    assert first_ink['unfold_seconds'] == -1


def test_timing_does_not_retime_background_or_frame_jitter():
    project = mixed_media_composition()
    first = np.asarray(render_sequence_frame(compile_composition(project), 1., (240, 240)))
    project['effects']['ink_bloom'] = {'mode': 'recipe', 'params': {'ink_bloom.motion_speed': 2.}}
    second = np.asarray(render_sequence_frame(compile_composition(project), 1., (240, 240)))
    assert np.array_equal(first[:20, :20], second[:20, :20])
    assert not np.array_equal(first[60:180, 60:180], second[60:180, 60:180])
    assert not project['effects'].get('frame_jitter')
