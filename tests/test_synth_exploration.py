"""Snapshots recover complete behavior; auditions isolate one selected effect."""
import copy
import json
from pathlib import Path

import pytest

from synth_composition import compile_composition, load_composition, normalize_composition, save_composition
from synth_creative import CREATIVE_CONTROLS
from synth_exploration import capture_snapshot, comparison_problem, content, remove_snapshot, restore_snapshot, vary_effect
from synth_sequence import render_sequence_frame
from synth_starting_points import new_piece
from synth_studies import save_study, study_composition
from synth_video import video_composition, check_source
from test_synth_creative import animated
from test_synth_video import clip
from synth_comparison_preview import ComparisonFrames


def pixels(project, t=.2):
    return render_sequence_frame(compile_composition(project), t, (96, 72)).tobytes()


def test_snapshot_save_restore_recovers_full_piece_and_does_not_nest(tmp_path):
    original = animated('tape'); original['master']['contrast'] = 1.2
    original['sections'][0]['loops'] = 2
    captured, identifier = capture_snapshot(original, 'Green take')
    second, _ = capture_snapshot(captured, 'Another take')
    assert all('snapshots' not in item['document'] for item in second['snapshots'])
    assert compile_composition(original) == compile_composition(second)
    edited = vary_effect(second, 'tape', 'strong', ['damage'], 65)
    edited['canvas']['width'] = 1080; edited['fps'] = 20
    edited['sections'][0]['duration'] = 5.; edited['master']['contrast'] = .8
    edited['source']['states']['s0']['overrides']['slab.width'] = .2
    path = tmp_path / 'piece.json'; save_composition(path, edited)
    reopened = load_composition(path); restored = restore_snapshot(reopened, identifier)
    assert content(restored) == normalize_composition(original)
    assert restored['snapshots'] == second['snapshots']
    assert pixels(restored) == pixels(original)
    assert len(remove_snapshot(restored, identifier)['snapshots']) == 1
    assert 'snapshots' not in remove_snapshot(captured, identifier)
    assert 'snapshots' not in new_piece('shape')


@pytest.mark.parametrize('effect', tuple(CREATIVE_CONTROLS))
def test_variation_is_deterministic_scoped_and_preserves_clocks_and_other_effects(effect):
    project = animated(effect)
    project['effects']['bloom'] = {'mode': 'on', 'params': {'bloom.strength': .4}}
    project['sections'].append(dict(copy.deepcopy(project['sections'][0]), id='second'))
    original = copy.deepcopy(project); keys = [CREATIVE_CONTROLS[effect][0].key]
    varied = vary_effect(project, effect, 'moderate', keys, 527, 'second')
    assert varied == vary_effect(project, effect, 'moderate', keys, 527, 'second')
    assert project == original and varied['effects'] == project['effects']
    assert varied['sections'][0] == project['sections'][0]
    assert {k: v for k, v in varied['sections'][1].items() if k != 'effects'} == {k: v for k, v in project['sections'][1].items() if k != 'effects'}
    for key in ('seed', 'source', 'geometry', 'master', 'canvas', 'fps', 'ink_timing'):
        assert varied[key] == project[key]
    creative = varied['sections'][1]['effects'][effect]['creative']
    assert set(creative['values']) == set(keys)
    assert creative['variation'] == {'seed': 527, 'amount': 'moderate', 'controls': keys}
    before, after = compile_composition(project), compile_composition(varied)
    assert before['cues'] == after['cues'] and not comparison_problem(before, after)


def test_local_variation_starts_from_parent_and_locked_controls_stay_inherited():
    project = animated('tape')
    project['effects']['tape'] = {'mode': 'recipe', 'params': {}, 'creative': {'version': 1, 'values': {'damage': 1.7, 'cadence': .5}}}
    varied = vary_effect(project, 'tape', 'subtle', ['damage'], 67, 'section-1')
    creative = varied['sections'][0]['effects']['tape']['creative']
    assert 1.6 <= creative['values']['damage'] <= 1.8
    assert 'cadence' not in creative['values'] and varied['effects'] == project['effects']
    assert varied == vary_effect(project, 'tape', 'subtle', ['damage'], 67, 'section-1')


@pytest.mark.parametrize('change,expected', [('canvas', 'canvas'), ('fps', 'FPS'), ('duration', 'duration'), ('time_map', 'clocks')])
def test_incompatible_frame_coordinates_have_an_explanation(change, expected):
    first = compile_composition(animated()); second = copy.deepcopy(first)
    if change == 'canvas': second['canvas']['width'] += 1
    elif change == 'time_map': second['time_map'] = [{'start': 0., 'end': 3., 'effects_rate': .5}]
    else: second[change] += 1
    assert expected in comparison_problem(first, second)


def test_snapshot_video_is_packaged_once_even_when_working_piece_is_generated(clip, tmp_path):
    video, identifier = capture_snapshot(video_composition(clip), 'Footage take')
    generated = new_piece('shape'); generated['snapshots'] = video['snapshots']
    root = tmp_path / 'studies'; study = save_study(generated, 'Portable snapshots', root)
    reopened = study_composition(study, root); restored = restore_snapshot(reopened, identifier)
    assert check_source(restored['footage']).is_file()
    assert Path(restored['footage']['path']).is_relative_to(root)
    assert compile_composition(restored)['footage']['path'] == restored['footage']['path']
    duplicated, _ = capture_snapshot(video, 'Same media')
    study = save_study(duplicated, 'Shared video', root)
    folder = root / study.split(':')[1]
    assert len(list((folder / 'media').iterdir())) == 1
    for item in study_composition(study, root)['snapshots']: check_source(item['document']['footage'])


@pytest.mark.parametrize('bad', ['nested', 'duplicate', 'date', 'name', 'version', 'too-many'])
def test_snapshot_schema_rejects_unsafe_or_ambiguous_libraries(bad):
    project, _ = capture_snapshot(animated(), 'A'); item = project['snapshots'][0]
    if bad == 'nested': item['document']['snapshots'] = []
    elif bad == 'duplicate': project['snapshots'].append(copy.deepcopy(item))
    elif bad == 'date': item['created_at'] = '2026-10-02'
    elif bad == 'name': item['name'] = ' '
    elif bad == 'version': item['version'] = True
    else: project['snapshots'] *= 33
    with pytest.raises(ValueError): normalize_composition(project)


def test_recorded_variation_and_snapshot_pixels_survive_save_open(tmp_path):
    project = vary_effect(animated(), 'tape', 'strong', ['damage', 'color'], 8182)
    project, identifier = capture_snapshot(project, 'Wear')
    path = tmp_path / 'piece.json'; save_composition(path, project)
    reopened = load_composition(path)
    assert reopened == project and pixels(restore_snapshot(reopened, identifier)) == pixels(project)
    record = reopened['effects']['tape']['creative']['variation']
    assert record['seed'] == 8182
    assert json.loads(path.read_text())['snapshots'][0]['document']['effects']['tape']['creative']['variation'] == record


def test_comparison_cache_is_separate_bounded_and_accounts_for_pending_packets():
    cache = ComparisonFrames(budget=18)
    cache.switch('A'); cache.anchor(0)
    cache.put(0, ((2, 1), b'AAAAAA')); cache.put(1, ((2, 1), b'aaaaaa'))
    cache.switch('B'); assert not cache.items
    cache.put(0, ((2, 1), b'BBBBBB'))
    assert cache.bytes == 18
    cache.reserve(6, (0,)); assert cache.bytes + cache.reserved <= 18
    cache.release(6); cache.switch('A')
    assert cache.get(0)[1] == b'AAAAAA' and cache.get(1) is None
    cache.switch('B'); assert cache.get(0)[1] == b'BBBBBB'
    cache.clear(); assert cache.bytes == 0 and not cache.banks
