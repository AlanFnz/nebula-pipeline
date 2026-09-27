import copy
import json

import pytest

from synth import render_synth_frame
from synth_composition import compile_composition, load_composition, mixed_media_composition, normalize_composition, save_composition
from synth_effects import effect_preset
from synth_print import bloom_phase
from synth_sequence import _state_preset, render_sequence_frame
from synth_shared_timing import PROFILE_PATHS, edit_shared_timing, restore_shared_timing, without_timing


def presets(project):
    sequence = compile_composition(project)
    return [_state_preset(sequence, cue['state']) for cue in sequence['cues']]


def ink(preset):
    return next(entry['params'] for entry in preset['modules'] if entry['id'] == 'ink_bloom')


def test_legacy_section_edits_migrate_once_without_changing_artwork_or_source(tmp_path):
    old = mixed_media_composition(); old.pop('ink_timing')
    old['sections'][0]['effects']['ink_bloom'] = {'mode': 'recipe', 'params': {'ink_bloom.unfold_seconds': .4, 'ink_bloom.count': 4}}
    old['sections'][1]['effects']['ink_bloom'] = {'mode': 'recipe', 'params': {'ink_bloom.unfold_seconds': 2., 'ink_bloom.palette': 1}}
    before = copy.deepcopy(old)
    path = tmp_path / 'old.json'; path.write_text(json.dumps(old))
    project = load_composition(path)
    assert project['ink_timing']['ink_bloom.unfold_seconds'] == .4
    assert project['sections'][0]['effects']['ink_bloom']['params'] == {'ink_bloom.count': 4}
    assert project['sections'][1]['effects']['ink_bloom']['params'] == {'ink_bloom.palette': 1}
    assert project['source'] == before['source'] and old == before
    assert normalize_composition(project) == project
    assert all(ink(p)['unfold_seconds'] == .4 for p in presets(project))
    save_composition(path, project); assert load_composition(path) == project


def test_existing_global_timing_wins_over_conflicting_old_section_overrides():
    project = mixed_media_composition()
    project['effects']['ink_bloom'] = {'mode': 'recipe', 'params': {'ink_bloom.unfold_seconds': .7}}
    for section in project['sections']:
        section['effects']['ink_bloom'] = {'mode': 'recipe', 'params': {'ink_bloom.unfold_seconds': 3.}}
    project = normalize_composition(project)
    assert project['ink_timing']['ink_bloom.unfold_seconds'] == .7
    assert all(not s['effects'] for s in project['sections'])
    assert all(ink(p)['unfold_seconds'] == .7 for p in presets(project))


def test_one_clock_crosses_the_section_boundary_despite_scene_speed_and_fps():
    project = mixed_media_composition()
    project['source']['states']['second']['overrides'].update(speed=3., treatment_fps=9)
    edit_shared_timing(project, 'ink_bloom.unfold_seconds', .4)
    first, second = presets(project)
    assert all(ink(first)[path.split('.')[1]] == ink(second)[path.split('.')[1]] for path in PROFILE_PATHS)
    assert first['speed'] == 1. and second['speed'] == 3.
    for time in (0., .13, .37, 3.4, 3.5, 53 / 15, 3.6, 6.8, 10000.):
        assert bloom_phase(time, ink(first), first['speed']) == bloom_phase(time, ink(second), second['speed'])
    # Isolate one identical figure: section clock settings must not change its pixels.
    second['modules'] = copy.deepcopy(first['modules'])
    for preset in (first, second):
        preset['modules'] = [m for m in preset['modules'] if m['id'] == 'ink_bloom']
    for time in (.13, .37, 3.5, 3.6):
        assert render_synth_frame(first, time_seconds=time, size=(160, 160)).tobytes() == render_synth_frame(second, time_seconds=time, size=(160, 160)).tobytes()


def test_a_cut_between_identical_looks_does_not_reset_the_animation():
    project = mixed_media_composition()
    project['source']['states']['second'] = copy.deepcopy(project['source']['states']['first'])
    project['source']['cues'][1]['transition'] = 'cut'
    edit_shared_timing(project, 'ink_bloom.folded_seconds', 2.)
    sequence = compile_composition(project)
    continuous = copy.deepcopy(sequence); continuous['cues'] = [continuous['cues'][0]]
    boundary = round(sequence['cues'][1]['time'] * project['fps'])
    for frame in range(boundary - 4, boundary + 5):
        assert render_sequence_frame(sequence, frame / 15, (160, 160)).tobytes() == render_sequence_frame(continuous, frame / 15, (160, 160)).tobytes()


def test_look_presets_cannot_reset_shared_timing_and_restore_recovers_original_frames():
    project = mixed_media_composition()
    original = render_sequence_frame(compile_composition(project), 4.6, (180, 180)).tobytes()
    edit_shared_timing(project, 'ink_bloom.unfold_seconds', .3)
    profile = copy.deepcopy(project['ink_timing'])
    project['sections'][1]['effects']['ink_bloom'] = without_timing(effect_preset('ink_bloom', 2))
    project = normalize_composition(project)
    assert project['ink_timing'] == profile
    assert all(ink(p)['unfold_seconds'] == .3 for p in presets(project))
    project['sections'][1]['effects'].clear(); restore_shared_timing(project)
    assert render_sequence_frame(compile_composition(project), 4.6, (180, 180)).tobytes() == original
    assert [s['duration'] for s in project['sections']] == [53 / 15] * 2


def test_complete_cycle_sections_resize_together_and_the_boundary_stays_closed():
    project = mixed_media_composition()
    edit_shared_timing(project, 'ink_bloom.unfold_seconds', .4)
    sequence = compile_composition(project)
    p = presets(project)[0]; params = ink(p)
    loop = sum(params[key] for key in ('unfold_seconds', 'unfolded_seconds', 'fold_seconds', 'folded_seconds'))
    boundary = sequence['cues'][1]['time']
    assert boundary == round(loop * project['fps']) / project['fps']
    assert sequence['duration'] == round(2 * loop * project['fps']) / project['fps']
    for time in (boundary - 1 / 15, boundary, boundary + 1 / 15):
        assert bloom_phase(time, params)[2] == 0
    edit_shared_timing(project, 'ink_bloom.motion_speed', 2.)
    assert compile_composition(project)['duration'] == round(loop * project['fps']) / project['fps']


def test_multiple_cycles_round_cumulative_boundaries_without_drift():
    project = mixed_media_composition()
    project['sections'] = [dict(copy.deepcopy(project['sections'][i % 2]), id=f'section-{i}') for i in range(8)]
    for section in project['sections']: section['duration'] *= 2
    edit_shared_timing(project, 'ink_bloom.unfold_seconds', .417)
    p = project['ink_timing']
    loop = sum(p[f'ink_bloom.{key}'] for key in ('unfold_seconds', 'unfolded_seconds', 'fold_seconds', 'folded_seconds'))
    boundary = 0
    for index, section in enumerate(project['sections'], 1):
        boundary += round(section['duration'] * project['fps'])
        assert boundary == round(index * 2 * loop * project['fps'])


def test_manually_arranged_noncycle_sections_retain_their_lengths():
    project = mixed_media_composition()
    project['sections'][0]['duration'] = 2.
    before = [s['duration'] for s in project['sections']]
    edit_shared_timing(project, 'ink_bloom.unfold_seconds', .4)
    assert [s['duration'] for s in project['sections']] == before


@pytest.mark.parametrize('value', [[], {'wrong': 1}, {'ink_bloom.unfold_seconds': float('nan')}, {'ink_bloom.cadence': 0}])
def test_invalid_shared_timing_is_rejected(value):
    project = mixed_media_composition(); project['ink_timing'] = value
    with pytest.raises(ValueError): normalize_composition(project)
