import copy

import numpy as np

from synth import MODULE_BY_ID, default_synth_preset
from synth_canvas import resize_canvas, format_canvas
from synth_composition import compile_composition, load_composition, save_composition
from synth_particle_mesh import head_mesh
from synth_particles import _population, render_particles
from synth_profile import render_silhouette
from synth_sequence import render_sequence_frame
from synth_starters import starter_composition


def test_scan_is_finite_oriented_and_has_usable_surface_normals():
    triangles, normals, cumulative = head_mesh('doryphoros-head')
    assert len(triangles) == 32000
    assert np.isfinite(triangles).all() and np.isfinite(normals).all()
    assert np.allclose(np.linalg.norm(normals, axis=2), 1., atol=1e-6)
    assert np.all(np.diff(cumulative) > 0) and cumulative[-1] == 1
    # The nose projects forward (+Z), and the cut base is below the chin.
    assert triangles[..., 1].min() < -1.2 and triangles[..., 1].max() > 1.
    tip = triangles.reshape(-1, 3)[np.argmax(triangles[..., 2])]
    assert -.6 < tip[1] < .3 and abs(tip[0]) < .3
    assert not triangles.flags.writeable and not normals.flags.writeable


def test_classical_silhouette_keeps_shape_when_canvas_grows_and_moves_as_one():
    settings = {s.key: s.default for s in MODULE_BY_ID['silhouette'].params}
    settings.update(model=2, scale=.3, center_x=.5, center_y=.5,
                    neck_length=0., neck_fullness=0., softness=0.)
    preset = default_synth_preset(); preset.update(width=320, height=240)
    original = render_silhouette(np.zeros((240, 320, 3)), settings, 0, preset, 1)
    portrait = dict(preset, width=320, height=480, reference={'width': 320, 'height': 240, 'framing': 'native'}, framing='preserve')
    grown = render_silhouette(np.zeros((480, 320, 3)), settings, 0, portrait, 1)
    assert np.array_equal(original, grown[120:360])
    moved = render_silhouette(np.zeros_like(original), settings, 0, dict(preset, object_x=20.), 1)
    assert np.array_equal(original[:, :-20], moved[:, 20:])
    other = render_silhouette(np.zeros_like(original), dict(settings, model=0), 0, preset, 1)
    assert not np.array_equal(original, other)


def test_classical_particles_have_stable_identities_and_support_neck_feather():
    points, normals, _, _ = _population(5, 1000, 37)
    assert np.array_equal(points, _population(5, 2000, 37)[0][:1000])
    assert np.isfinite(normals).all()
    settings = {s.key: s.default for s in MODULE_BY_ID['particles'].params}
    settings.update(attractor=5, count=2000, breathing=0., assembly=1., neck_fade=0.)
    preset = default_synth_preset(); preset.update(width=160, height=128)
    black = np.zeros((128, 160, 3))
    original = render_particles(black, settings, 0, preset, 37)
    feathered = render_particles(black, dict(settings, neck_fade=1.), 0, preset, 37)
    assert feathered.sum() < original.sum()
    assert np.array_equal(original, render_particles(black, settings, 0, preset, 37))


def test_classical_starter_roundtrip_all_states_and_story_format(tmp_path):
    original = starter_composition('profile-clear'); before = copy.deepcopy(original)
    project = starter_composition('profile-doryphoros')
    assert project['sections'] == original['sections']
    assert compile_composition(project)['duration'] == 8
    for state in project['source']['states'].values():
        assert state['overrides']['silhouette.model'] == 2
        assert state['overrides']['silhouette.definition'] == 0
    project['canvas'] = resize_canvas(project['canvas'], format_canvas('stories'))
    path = tmp_path / 'doryphoros.json'; save_composition(path, project)
    loaded = load_composition(path); assert loaded == project
    expected = render_sequence_frame(compile_composition(project), .2, (180, 320))
    assert expected.tobytes() == render_sequence_frame(compile_composition(loaded), .2, (180, 320)).tobytes()
    assert starter_composition('profile-clear') == before
