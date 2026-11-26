"""Fold geometry, movable gradient stops and their common preview/export clock."""
import copy
import json

import numpy as np
import pytest

from nebula.documents.synth_composition import compile_composition, load_composition, save_composition, stretch_section
from nebula.documents.synth_media import render_output_frame
from nebula.documents.synth_sequence import render_sequence_frame
from nebula.sources.synth_folded_gradient import decode_design, default_design, validate_design
from test_synth_radial_gradients import composition, frame
from test_synth_effects_editor_integration import make_window


def test_mesh_interpolates_in_both_directions_and_extends_beyond_the_authored_end(tmp_path):
    design = json.dumps(default_design())
    settings = dict(pattern=2, petals=8, cycle=4., rotation=0., softness=0., fold_design=design)
    project = composition(**settings)
    path = tmp_path / 'folds.nebula'
    save_composition(path, project)
    assert load_composition(path) == project
    opposite = composition(direction=1, **settings)
    assert frame(opposite, .75) == frame(project, 3.25)
    held = composition(direction=2, motion_phase=.25, **settings)
    assert frame(held, 3.) == frame(project, 1.)
    longer = stretch_section(project, project['sections'][0]['id'], 8., 'smart')
    seq = compile_composition(longer)
    for t in (3.75, 4., 4.25, 7.75):
        image = render_sequence_frame(seq, t, (96, 80))
        expected = frame(project, t if t <= 4 else 8 - t)
        assert image.tobytes() == expected
        assert render_output_frame(None, seq, round(t * seq['fps']), (96, 80), None).tobytes() == expected


@pytest.mark.parametrize('direction', (0, 1))
def test_outward_pulse_preserves_first_pass_and_continues_on_seek_and_export(direction, tmp_path):
    cycle_frames = 95
    settings = dict(pattern=2, petals=8, cycle=cycle_frames/24, direction=direction,
                    rotation=0., softness=0.)
    original = composition(**settings)
    project = composition(fold_repeat=1, **settings)
    longer = stretch_section(project, project['sections'][0]['id'], 12., 'smart')
    path = tmp_path / 'extended.nebula'
    save_composition(path, longer)
    seq = compile_composition(load_composition(path))

    def exported(index):
        return render_output_frame(None, seq, index, (96, 80), None).tobytes()

    for index in (0, 47, 94, 95):
        assert exported(index) == frame(original, index / 24)
    assert exported(2 * cycle_frames) == exported(cycle_frames)
    for offset in (30, 8, 1):
        index = cycle_frames + offset
        assert exported(index) == exported(index + cycle_frames)
        assert exported(index) == render_sequence_frame(seq, index / 24, (96, 80)).tobytes()
        assert exported(index) != frame(original, (cycle_frames - offset) / 24)
    assert exported(cycle_frames + 30) == frame(original, 30 / 24)


def test_next_pulse_opens_at_the_center_and_respects_a_held_pose():
    design = default_design()
    for pose, color in zip(design['poses'], ((240, 50, 30), (30, 65, 220))):
        for wedge in pose['wedges']:
            for guide in wedge:
                for knot in guide:
                    knot[1:] = color
    settings = dict(pattern=2, cycle=2., rotation=0., softness=0., fold_repeat=1,
                    fold_design=json.dumps(design))
    project = composition(**settings)
    pixels = lambda t: np.frombuffer(frame(project, t), np.uint8).reshape(80, 96, 3)
    opening = pixels(2.125)
    assert opening[40, 48, 0] > opening[40, 48, 2]
    np.testing.assert_array_equal(opening[0, 0], pixels(2.)[0, 0])
    held = composition(direction=2, motion_phase=.2, **settings)
    assert frame(held, 3.) == frame(held, 0.)
    design['poses'] = design['poses'][:1]
    single = composition(**dict(settings, fold_design=json.dumps(design)))
    assert frame(single, 2.125) == frame(single, 0.)


def test_even_pacing_redistributes_bunched_poses_and_starts_at_the_selected_pose():
    design = default_design()
    design['inks'] = [[0, 0, 0]] * 8
    design['poses'].insert(1, copy.deepcopy(design['poses'][0]))
    for pose, at, shade in zip(design['poses'], (0., .125, 1.), (20, 120, 220)):
        pose['at'] = at
        for wedge in pose['wedges']:
            for guide in wedge:
                for knot in guide:
                    knot[1:] = [shade] * 3
    settings = dict(pattern=2, cycle=2., rotation=0., softness=0., fold_design=json.dumps(design))
    settings.update({f'stop_{i}_light': 0. for i in range(1, 9)})
    authored = composition(**settings)
    even = composition(fold_pacing=1, **settings)
    times = np.arange(9) / 4
    before = np.array([frame(authored, t)[0] for t in times])
    after = np.array([frame(even, t)[0] for t in times])
    assert np.ptp(np.diff(before)) > 50
    assert np.ptp(np.diff(after)) <= 2
    assert list(after[[0, -1]]) == list(before[[0, -1]])

    for direction, phase in ((0, .125), (1, .875), (2, .125)):
        offset = composition(fold_pacing=1, direction=direction, motion_phase=phase, **settings)
        assert frame(offset, 0.) == frame(authored, .25)
        if direction == 2:
            assert frame(offset, 1.75) == frame(offset, 0.)


@pytest.mark.parametrize('direction', (0, 1))
def test_even_outward_cycle_closes_and_continues_when_extended(direction, tmp_path):
    settings = dict(pattern=2, petals=8, cycle=2., direction=direction, rotation=0., softness=0.)
    authored = composition(**settings)
    project = composition(fold_pacing=1, fold_repeat=1, **settings)
    longer = stretch_section(project, project['sections'][0]['id'], 8., 'smart')
    path = tmp_path / 'even.nebula'
    save_composition(path, longer)
    seq = compile_composition(load_composition(path))

    def exported(index):
        return render_output_frame(None, seq, index, (96, 80), None).tobytes()

    assert exported(0) == frame(authored, 0.)
    for index in (1, 27, 46, 47, 0):
        assert exported(index + 96) == exported(index)
        assert exported(index + 48) == render_sequence_frame(seq, index / 24, (96, 80)).tobytes()
    near_start = np.frombuffer(exported(47), np.uint8).astype(float)
    start = np.frombuffer(exported(0), np.uint8).astype(float)
    far = np.frombuffer(exported(24), np.uint8).astype(float)
    assert 0 < np.abs(near_start - start).mean() < np.abs(far - start).mean() / 3


@pytest.mark.parametrize('direction', (0, 1))
@pytest.mark.parametrize('pacing', (0, 1))
def test_loop_poses_replays_the_drawn_join_on_seek_export_and_extend(direction, pacing):
    design = default_design()
    design['poses'][1]['at'] = .25
    design['poses'].append(dict(design['poses'][0], at=1.))
    settings = dict(pattern=2, fold_design=json.dumps(design), cycle=2.,
                    rotation=0., softness=0., direction=direction, fold_pacing=pacing)
    first_pass = compile_composition(composition(**settings))
    project = composition(fold_repeat=2, **settings)
    seq = compile_composition(stretch_section(project, project['sections'][0]['id'], 8., 'smart'))
    for index in (47, 0, 1, 8, 21):
        expected = render_sequence_frame(first_pass, index / 24, (96, 80)).tobytes()
        assert render_sequence_frame(seq, (48 + index) / 24, (96, 80)).tobytes() == expected
        assert render_output_frame(None, seq, 96 + index, (96, 80), None).tobytes() == expected
    held = composition(**dict(settings, direction=2, motion_phase=.25), fold_repeat=2)
    assert frame(held, 3.) == frame(held, 0.)


def test_vector_bands_fan_and_palette_are_live_and_old_patterns_ignore_them():
    source = dict(pattern=2, petals=8, rotation=0., softness=0.)
    base = frame(composition(**source), 1.)
    for key in ('core_scale', 'ray_scale', 'aperture_scale', 'ray_sharpness', 'fan_width'):
        assert frame(composition(**source, **{key: 1.7}), 1.) != base
    assert frame(composition(**source, stop_3_light=.12), 1.) != base
    for count in (3, 9, 48):
        assert frame(composition(**dict(source, petals=count)), 1.) != base
    for mode in (0, 1):
        assert frame(composition(pattern=mode), .25) == frame(composition(pattern=mode, ray_scale=2.), .25)


def test_gradient_design_rejects_bad_topology_and_supports_a_single_pose():
    design = default_design()
    design['poses'] = design['poses'][:1]
    assert decode_design(json.dumps(design))[1].shape[0] == 1
    for mutation in ('decreasing', 'stamp', 'shape', 'times'):
        bad = copy.deepcopy(design)
        if mutation == 'decreasing':
            bad['poses'][0]['wedges'][0][0][1][0] = 0
        elif mutation == 'stamp':
            bad['poses'][0]['wedges'][0][0][2][1] = np.inf
        elif mutation == 'shape':
            bad['poses'][0]['wedges'][0].pop()
        else:
            bad['poses'][0]['at'] = .5
        with pytest.raises(ValueError):
            validate_design(json.dumps(bad))


def test_object_exposes_the_palette_and_only_applicable_fold_controls(make_window):
    window = make_window(composition=composition(pattern=2))
    panel = window.composer.object_panel
    window.composer.look_tabs.setCurrentWidget(panel)
    assert 'radial_bloom.fold_design' in panel.object_eligible
    assert 'radial_bloom.ray_scale' in panel.object_eligible
    assert 'radial_bloom.fold_repeat' in panel.object_eligible
    assert 'radial_bloom.fold_pacing' in panel.object_eligible
    assert 'radial_bloom.copy_angle' not in panel.object_eligible
    assert 'radial_bloom.stop_1_position' not in panel.object_eligible
    assert panel.controls['radial_bloom.petals'].label.text() == 'Ray count'
    assert panel.palette_selector.isVisible()
