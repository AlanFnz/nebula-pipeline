import copy
import json
import subprocess

import numpy as np
import pytest

from synth import MODULE_BY_ID, default_synth_preset, render_synth_frame
from synth_canvas import format_canvas
from synth_composition import compile_composition, ink_bloom_composition, load_composition, save_composition
from synth_effects import effect_preset
from synth_print import bloom_phase, render_ink_bloom, render_print_surface
from synth_media import export_synth_video
from synth_sequence import _state_preset, render_sequence_frame


def settings(module, **overrides):
    return {**{p.key: p.default for p in MODULE_BY_ID[module].params}, **overrides}


def test_print_effects_are_exact_bypasses_and_do_not_mutate_their_input():
    source = np.random.default_rng(3).random((80, 100, 3)).astype(np.float32)
    original = source.copy()
    assert np.array_equal(render_ink_bloom(source, settings('ink_bloom', opacity=0), .5, 1, 4), source)
    assert np.array_equal(render_print_surface(source, settings('print_surface', mix=0), .5, 1, 4), source)
    assert not np.array_equal(render_print_surface(source, settings('print_surface'), .5, 1, 4), source)
    assert np.array_equal(source, original)


@pytest.mark.parametrize('module,renderer', [('ink_bloom', render_ink_bloom), ('print_surface', render_print_surface)])
def test_print_effects_hold_their_cadence_and_support_random_access(module, renderer):
    source = np.full((100, 100, 3), .1, dtype=np.float32)
    p = settings(module)
    first = renderer(source, p, .001, 1, 13)
    assert np.array_equal(first, renderer(source, p, .05, 1, 13))
    assert not np.array_equal(first, renderer(source, p, .07, 1, 13))
    distant = renderer(source, p, 1_000_000, 1, 13)
    assert np.isfinite(distant).all()
    assert np.array_equal(first, renderer(source, p, .001, 1, 13))
    assert np.array_equal(renderer(source, p, 0, 0, 13), renderer(source, p, 10, 0, 13))


def test_bloom_opens_and_refolds_with_controllable_timing_and_manual_opening():
    p = settings('ink_bloom')
    assert bloom_phase(0, p)[2] == 0
    assert bloom_phase(1.6, p)[2] == 1
    assert bloom_phase(3.2, p)[2] == 0
    assert bloom_phase(.8, dict(p, open_start=50))[2] == 0
    assert bloom_phase(1.6, dict(p, cycle=0, opening=.37))[2] == .37
    source = np.zeros((180, 180, 3), dtype=np.float32)
    closed = render_ink_bloom(source, p, 0, 1, 13)
    opened = render_ink_bloom(source, p, 1.6, 1, 13)
    assert np.count_nonzero(opened.max(axis=2)) > np.count_nonzero(closed.max(axis=2)) * 3
    assert np.array_equal(closed, render_ink_bloom(source, p, p['period'], 1, 13))


def test_ink_geometry_uses_the_short_edge_without_stretching_or_off_center_framing():
    p = settings('ink_bloom', registration=0)
    square = render_ink_bloom(np.zeros((180, 180, 3), dtype=np.float32), p, 1.7, 1, 15)
    portrait = render_ink_bloom(np.zeros((320, 180, 3), dtype=np.float32), p, 1.7, 1, 15)
    assert np.allclose(square, portrait[70:250], atol=1e-5)
    y, x = np.where(portrait.max(axis=2) > .2)
    assert abs((x.min() + x.max()) / 2 - 90) < 18
    assert abs((y.min() + y.max()) / 2 - 160) < 18


def test_starter_is_one_editable_gesture_and_print_can_treat_an_existing_study(tmp_path):
    project = ink_bloom_composition()
    assert len(project['sections']) == len(project['source']['states']) == len(project['source']['cues']) == 1
    assert project['fps'] == 15
    path = tmp_path / 'ink.json'; save_composition(path, project)
    assert load_composition(path) == project
    before = copy.deepcopy(project)
    project['effects']['ink_bloom'] = effect_preset('ink_bloom')
    project['effects']['ink_bloom']['params'].update({'ink_bloom.count': 4, 'ink_bloom.points': 6, 'ink_bloom.palette': 1})
    project['canvas'] = format_canvas('stories')
    seq = compile_composition(project)
    image = np.asarray(render_sequence_frame(seq, 1.6, (180, 320)))
    for patch in (image[:24, :24], image[:24, -24:], image[-24:, :24], image[-24:, -24:]):
        assert patch.mean() > 10 and patch.std() > .2
    assert project['source'] == before['source']
    preset = _state_preset(seq, seq['cues'][0]['state'])
    assert next(x for x in preset['modules'] if x['id'] == 'ink_bloom')['params']['count'] == 4
    # The paper treatment also works on luminous sources, with no ink generator.
    preset = default_synth_preset()
    original = render_synth_frame(preset, time_seconds=.4, size=(180, 144))
    next(x for x in preset['modules'] if x['id'] == 'print_surface')['enabled'] = True
    treated = render_synth_frame(preset, time_seconds=.4, size=(180, 144))
    assert treated.tobytes() != original.tobytes()


def test_starter_exports_53_held_frames_at_15fps(tmp_path):
    output = tmp_path / 'ink.mp4'
    seq = compile_composition(ink_bloom_composition())
    export_synth_video(default_synth_preset(), output, sequence=seq, size=(180, 180))
    stream = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'stream=width,height,r_frame_rate,nb_frames', '-of', 'json', str(output)], text=True))['streams'][0]
    assert (stream['width'], stream['height'], stream['r_frame_rate'], stream['nb_frames']) == (180, 180, '15/1', '53')


def test_middle_fold_crosses_the_outer_planes_and_reverse_ink_preserves_front_colors():
    source = np.zeros((240, 240, 3), dtype=np.float32)
    p = settings('ink_bloom', count=1, tumble=0., tilt=0., rotation=0., fan=0.)
    extents = []
    for fold in (0., 1.):
        result = render_ink_bloom(source, dict(p, center_fold=fold), 16 / 15, 1, 18)
        y, x = np.where(result.max(axis=2) > .2)
        extents.append((np.ptp(x), np.ptp(y)))
    assert extents[0][1] > extents[0][0] * 3
    assert extents[1][0] > extents[1][1] * 3
    p = settings('ink_bloom', cycle=0., opening=1.)
    back = render_ink_bloom(source, dict(p, back_ink=1.), 0, 1, 18)
    multicolor_back = render_ink_bloom(source, dict(p, back_ink=0.), 0, 1, 18)
    assert not np.array_equal(back, multicolor_back)
    assert np.array_equal(render_ink_bloom(source, dict(p, back_ink=1.), 1.6, 1, 18), render_ink_bloom(source, dict(p, back_ink=0.), 1.6, 1, 18))


def test_saved_ink_recipe_retains_its_look_if_module_defaults_change(monkeypatch):
    from dataclasses import replace
    import synth
    project = ink_bloom_composition()
    before = render_sequence_frame(compile_composition(project), 1.6, (180, 180)).tobytes()
    changed = []
    for module in synth.MODULES:
        if module.id == 'ink_bloom':
            module = replace(module, params=tuple(replace(p, default=3) if p.key == 'count' else p for p in module.params))
        if module.id == 'print_surface':
            module = replace(module, params=tuple(replace(p, default=.2) if p.key == 'black_level' else p for p in module.params))
        changed.append(module)
    monkeypatch.setattr(synth, 'MODULES', tuple(changed))
    assert render_sequence_frame(compile_composition(project), 1.6, (180, 180)).tobytes() == before
