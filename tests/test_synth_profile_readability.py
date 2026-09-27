import numpy as np

from synth import MODULE_BY_ID, default_synth_preset
from synth_composition import compile_composition, load_composition, save_composition
from synth_particle_mesh import _head_mesh
from synth_profile import render_silhouette
from synth_sequence import render_sequence_frame
from synth_starters import starter_composition


def test_facial_definition_improves_profile_without_altering_skull_or_cached_mesh():
    p = {s.key: s.default for s in MODULE_BY_ID['silhouette'].params}
    preset = default_synth_preset(); preset.update(width=320, height=240)
    black = np.zeros((240, 320, 3), np.float32)
    mesh = _head_mesh(True)[0].copy()
    original = render_silhouette(black, p, 0., preset, 1)
    defined = render_silhouette(black, dict(p, definition=.65), 0., preset, 1)
    assert np.array_equal(original[:60], defined[:60])
    assert np.where(defined[..., 0] > .5)[1].min() < np.where(original[..., 0] > .5)[1].min()
    assert np.array_equal(_head_mesh(True)[0], mesh)
    assert np.array_equal(original, render_silhouette(black, p, 100., preset, 20))


def test_clear_profile_is_a_separate_editable_eight_second_recipe(tmp_path):
    original = starter_composition('profile-echoes')
    before = render_sequence_frame(compile_composition(original), .2, (240, 135)).tobytes()
    clear = starter_composition('profile-clear'); sequence = compile_composition(clear)
    assert sequence['duration'] == 8 and len(clear['sections']) == len(original['sections'])
    assert render_sequence_frame(sequence, .2, (240, 135)).tobytes() != before
    assert starter_composition('profile-echoes') == original
    save_composition(tmp_path / 'clear.json', clear)
    assert load_composition(tmp_path / 'clear.json') == clear
    assert render_sequence_frame(compile_composition(load_composition(tmp_path / 'clear.json')), .2, (240, 135)).tobytes() == render_sequence_frame(sequence, .2, (240, 135)).tobytes()
