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
    assert 'radial_bloom.copy_angle' not in panel.object_eligible
    assert 'radial_bloom.stop_1_position' not in panel.object_eligible
    assert panel.controls['radial_bloom.petals'].label.text() == 'Ray count'
    assert panel.palette_selector.isVisible()
