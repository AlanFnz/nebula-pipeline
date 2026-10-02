"""Creative adjustments preserve source animation, clocks and scope semantics."""
import copy

import numpy as np
import pytest

from synth import _smear
from synth_composition import compile_composition, load_composition, save_composition
from synth_creative import CREATIVE_CONTROLS
from synth_effects import normalize_effects, state_values
from synth_jitter import frame_pose
from synth_sequence import load_sequence, render_sequence_frame, save_sequence
from synth_starting_points import new_piece
from synth_subject import select_subject


def adjustment(**values):
    return dict(mode='recipe', params={}, creative=dict(version=1, values=values))


def animated(effect='tape'):
    project = new_piece('model', model='particles') if effect == 'particles' else new_piece('shape')
    source = project['source']; original = source['states']['blank']
    varying = {
        'tape': ('tape.tracking', (.025, .07, .01)),
        'frame_jitter': ('frame_jitter.x', (2., 7., 0.)),
        'ghosts': ('smear.ghosts', (2, 5, 9)),
        'particles': ('particles.dispersion', (.3, .7, .1)),
    }
    path, values = varying[effect]
    source['states'] = {}
    for index, value in enumerate(values):
        state = copy.deepcopy(original)
        module = 'smear' if effect == 'ghosts' else effect
        if index < 2 and module not in state['enabled']: state['enabled'].append(module)
        elif index == 2 and module in state['enabled']: state['enabled'].remove(module)
        state['overrides'][path] = value
        if effect == 'ghosts': state['overrides']['slab.ghost_opacity'] = 0.
        if effect == 'particles':
            state['overrides'].update({'particles.motion': 2, 'particles.breathing': 1., 'particles.period': 10., 'particles.phase': .5})
        source['states'][f's{index}'] = state
    source['cues'] = [dict(time=i, state=f's{i}', transition='cut', duration=0.) for i in range(3)]
    source['duration'] = 3.
    project['phrases']['custom']['end'] = 3.; project['sections'][0]['duration'] = 3.
    return project


@pytest.mark.parametrize('effect,key,factor,path,expected', [
    ('tape', 'damage', 1.5, 'tape.tracking', [.0375, .105, .015]),
    ('frame_jitter', 'distance', 2., 'frame_jitter.x', [4., 14., 0.]),
    ('ghosts', 'copies', 2, 'smear.ghosts', [4, 7, 10]),
    ('particles', 'distance', 1.5, 'particles.dispersion', [.45, 1.05, .15]),
])
def test_adjustments_preserve_changing_values_activation_and_cues(effect, key, factor, path, expected):
    project = animated(effect); original = copy.deepcopy(project)
    before = compile_composition(project)
    project['effects'][effect] = adjustment(**{key: factor})
    after = compile_composition(project)
    assert after['cues'] == before['cues']
    assert after['duration'] == before['duration'] and after['fps'] == before['fps']
    assert project['source'] == original['source']
    for state, previous, value in zip(after['states'].values(), before['states'].values(), expected):
        values, enabled = state_values(state)
        assert values[path] == pytest.approx(value)
        assert enabled == state_values(previous)[1]


@pytest.mark.parametrize('effect', tuple(CREATIVE_CONTROLS))
def test_neutral_and_restoration_recover_exact_frames(effect):
    project = animated(effect); sequence = compile_composition(project)
    original = [render_sequence_frame(sequence, t, (96, 72)).tobytes() for t in (.2, 1.2, 2.2)]
    project['effects'][effect] = adjustment(**{c.key: c.neutral for c in CREATIVE_CONTROLS[effect]})
    neutral = compile_composition(project)
    assert [render_sequence_frame(neutral, t, (96, 72)).tobytes() for t in (.2, 1.2, 2.2)] == original
    project['effects'][effect] = adjustment(**{CREATIVE_CONTROLS[effect][0].key: CREATIVE_CONTROLS[effect][0].maximum})
    changed = compile_composition(project)
    assert render_sequence_frame(changed, .2, (96, 72)).tobytes() != original[0]
    project['effects'][effect].pop('creative')
    restored = compile_composition(project)
    assert [render_sequence_frame(restored, t, (96, 72)).tobytes() for t in (.2, 1.2, 2.2)] == original


def test_global_inheritance_explicit_neutral_and_local_restore():
    project = animated('frame_jitter')
    project['sections'].append(dict(copy.deepcopy(project['sections'][0]), id='second'))
    project['effects']['frame_jitter'] = adjustment(distance=2., rotation=.5)
    project['sections'][1]['effects']['frame_jitter'] = adjustment(distance=1.)
    sequence = compile_composition(project)
    assert state_values(sequence['states']['section-1:s0'])[0]['frame_jitter.x'] == 4.
    second = state_values(sequence['states']['second:s0'])[0]
    assert second['frame_jitter.x'] == 2. and second['frame_jitter.rotation'] == .09
    project['sections'][1]['effects']['frame_jitter']['creative']['values'].pop('distance')
    assert state_values(compile_composition(project)['states']['second:s0'])[0]['frame_jitter.x'] == 4.


def test_fixed_values_are_the_base_and_collector_is_unadjusted_unbypassed():
    project = animated('tape'); project['effects']['tape'] = adjustment(damage=2.)
    project['effects']['tape']['params']['tape.tracking'] = .04
    base = {}; sequence = compile_composition(project, base_states=base)
    assert all(state_values(state)[0]['tape.tracking'] == .08 for state in sequence['states'].values())
    assert all(state_values(state)[0]['tape.tracking'] == .04 for state in base.values())
    assert compile_composition(project) == sequence
    project['effects']['tape']['bypassed'] = True
    sequence = compile_composition(project, base_states=base)
    assert all('tape' not in state_values(state)[1] for state in sequence['states'].values())
    assert 'tape' in state_values(base['section-1:s0'])[1]
    assert state_values(base['section-1:s0'])[0]['tape.tracking'] == .04


def test_jitter_distance_keeps_pose_sequence_and_cadence_controls_holds():
    project = animated('frame_jitter')
    original = state_values(compile_composition(project)['states']['section-1:s0'])[0]
    project['effects']['frame_jitter'] = adjustment(distance=1.5)
    adjusted = state_values(compile_composition(project)['states']['section-1:s0'])[0]
    params = lambda values: {k.removeprefix('frame_jitter.'): v for k, v in values.items() if k.startswith('frame_jitter.')}
    p, q = params(original), params(adjusted)
    for t in (.01, .09, .2, 100.):
        before, after = frame_pose(p, t, 1., 27), frame_pose(q, t, 1., 27)
        assert after[:2] == pytest.approx(np.array(before[:2]) * 1.5)
        assert after[2:] == before[2:]
    project['effects']['frame_jitter'] = adjustment(cadence=.5)
    slower = params(state_values(compile_composition(project)['states']['section-1:s0'])[0])
    assert frame_pose(slower, .01, 1., 27) == frame_pose(slower, .09, 1., 27)
    assert frame_pose(p, .01, 1., 27) != frame_pose(p, .09, 1., 27)


def test_particle_durations_and_disorder_do_not_change_cycle_or_model():
    project = animated('particles'); before = compile_composition(project)
    project['effects']['particles'] = adjustment(outward=.5, **{'return': 1.5}, disorder=.5)
    after = compile_composition(project)
    p = state_values(before['states']['section-1:s0'])[0]
    q = state_values(after['states']['section-1:s0'])[0]
    assert q['particles.expand_seconds'] == p['particles.expand_seconds'] * .5
    assert q['particles.gather_seconds'] == p['particles.gather_seconds'] * 1.5
    assert q['particles.chaos'] == p['particles.chaos'] * .5
    for key in ('period', 'phase', 'scale', 'yaw', 'pitch', 'attractor', 'axis_mode'):
        assert q[f'particles.{key}'] == p[f'particles.{key}']
    assert after['cues'] == before['cues']


def test_old_trail_math_is_unchanged_and_brightness_scales_all_copies():
    image = np.linspace(0, 1, 20 * 40 * 3, dtype=np.float32).reshape((20, 40, 3))
    p = dict(amount=.3, direction=1., ghosts=3)
    from synth import _zero_roll
    expected = image.copy()
    for i in range(1, 4): expected += _zero_roll(image, int(.3 * 40 * i / 3), 1) * (.22 / i)
    assert np.array_equal(_smear(image, p), expected)
    assert np.array_equal(_smear(image, dict(p, opacity=1.)), expected)
    assert np.array_equal(_smear(image, dict(p, opacity=0.)), image)
    assert np.allclose(_smear(image, dict(p, opacity=.5)) - image, (expected - image) * .5)


def test_save_open_and_detailed_copy_keep_adjusted_pixels(tmp_path):
    project = animated('tape'); project['effects']['tape'] = adjustment(damage=1.6, cadence=.5, color=.4)
    sequence = compile_composition(project)
    path = tmp_path / 'creative.json'; save_composition(path, project)
    reopened = load_composition(path)
    assert reopened['effects']['tape']['creative'] == project['effects']['tape']['creative']
    detailed = tmp_path / 'detailed.json'; save_sequence(detailed, sequence)
    for t in (1.2, .2, 2.2, .2):
        expected = render_sequence_frame(sequence, t, (96, 72)).tobytes()
        assert render_sequence_frame(compile_composition(reopened), t, (96, 72)).tobytes() == expected
        assert render_sequence_frame(load_sequence(detailed), t, (96, 72)).tobytes() == expected


def test_switching_sources_retains_particle_creative_values():
    project = animated('particles'); project['effects']['particles'] = adjustment(distance=1.5)
    switched = select_subject(select_subject(project, 'text'), 'particles')
    assert switched['effects']['particles']['creative']['values'] == {'distance': 1.5}


@pytest.mark.parametrize('creative', [
    None, [], {}, {'version': True, 'values': {}}, {'version': 2, 'values': {}},
    {'version': 1, 'values': []}, {'version': 1, 'values': {'unknown': 1}},
    {'version': 1, 'values': {'damage': True}}, {'version': 1, 'values': {'damage': float('nan')}},
    {'version': 1, 'values': {'damage': 3.}},
])
def test_invalid_creative_data_is_rejected(creative):
    with pytest.raises(ValueError): normalize_effects({'tape': {'creative': creative}})


def test_integer_count_and_unsupported_effect_validation():
    with pytest.raises(ValueError): normalize_effects({'ghosts': adjustment(copies=.5)})
    with pytest.raises(ValueError): normalize_effects({'bloom': adjustment(damage=1.)})
    assert normalize_effects({'tape': {}}) == {'tape': {'mode': 'recipe', 'params': {}}}
