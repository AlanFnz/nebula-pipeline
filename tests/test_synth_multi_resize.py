"""Proportional selection edits preserve independent clocks and loop budgets."""
import copy

import pytest

from synth_composition import (compile_composition, load_composition, normalize_composition,
                               proportional_section_durations, reference_composition,
                               save_composition, section_placements, stretch_sections)
from synth_retime import mapped_time
from synth_sequence import render_sequence_frame
from synth_video import video_composition
from test_synth_video import clip


def project():
    result = reference_composition(refined=True)
    result['sections'] = result['sections'][:3]
    for section, duration in zip(result['sections'], (2., 3., 1.)):
        section['duration'] = duration
    return normalize_composition(result)


def test_nonadjacent_stretch_keeps_unselected_clocks_and_round_trips(tmp_path):
    original = project()
    before = copy.deepcopy(original)
    selected = ['section-1', 'section-3']
    edited = stretch_sections(original, selected, 2.)
    assert original == before
    assert [section['duration'] for section in edited['sections']] == [4., 3., 2.]
    assert edited['sections'][1] == original['sections'][1]
    assert [edited['sections'][i]['effects_rate'] for i in (0, 2)] == [.5, .5]
    source = compile_composition(original)
    result = compile_composition(edited)
    for old_time, new_time in ((.32, .64), (2.32, 4.32), (5.32, 7.64)):
        assert mapped_time(result['time_map'], new_time) == pytest.approx(old_time)
        assert render_sequence_frame(result, new_time, (64, 48)).tobytes() == render_sequence_frame(source, old_time, (64, 48)).tobytes()
    path = tmp_path / 'selection.json'
    save_composition(path, edited)
    assert compile_composition(load_composition(path)) == result
    assert stretch_sections(edited, selected, .5) == original


def test_selection_limits_stop_at_a_common_scale_and_snap_to_frames():
    original = project()
    selected = ['section-1', 'section-2']
    compressed = stretch_sections(original, selected, -100.)
    assert [section['duration'] for section in compressed['sections']] == [.04, .08, 1.]
    expanded = stretch_sections(original, selected, 1e12)
    assert [section['duration'] for section in expanded['sections']] == [200., 300., 1.]
    edited = stretch_sections(original, selected, 1.137)
    for before, after in zip(original['sections'][:2], edited['sections'][:2]):
        assert after['duration'] * 25 == pytest.approx(round(after['duration'] * 25))
        assert abs(after['duration'] - before['duration'] * 1.137) <= .5 / 25
    assert stretch_sections(original, selected, 1.) == original


def test_arrangement_cap_accounts_for_all_loops_and_rounding():
    original = project()
    for section, duration, loops in zip(original['sections'], (10., 10.08, 100.), (2, 3, 1)):
        section.update(duration=duration, loops=loops)
    original['timeline_loops'] = [{'sections': ['section-1', 'section-2'], 'loops': 20}]
    selected = ['section-1', 'section-2']
    edited = stretch_sections(original, selected, 1e10)
    assert section_placements(edited)[-1][2] <= 3600
    assert section_placements(edited)[-1][2] >= 3596
    assert edited['timeline_loops'] == original['timeline_loops']
    assert [section['loops'] for section in edited['sections']] == [2, 3, 1]
    # The limiting result still has a common scale within half a frame.
    durations = [section['duration'] for section in edited['sections'][:2]]
    low = max((value - .5 / 25) / old for value, old in zip(durations, (10., 10.08)))
    high = min((value + .5 / 25) / old for value, old in zip(durations, (10., 10.08)))
    assert low <= high
    assert edited['sections'][2] == normalize_composition(original)['sections'][2]


@pytest.mark.parametrize('mode', ['effects', 'video'])
def test_video_selection_scales_existing_clocks_per_section(clip, mode):
    original = video_composition(clip)
    section = original['sections'][0]
    original['sections'] = [dict(copy.deepcopy(section), id=f'cut-{i}', duration=duration)
                            for i, duration in enumerate((.5, 1., 1.5))]
    original['sections'][0].update(effects_rate=.7, video_rate=.8)
    original = normalize_composition(original)
    edited = stretch_sections(original, ['cut-0', 'cut-2'], 2., mode)
    assert [section['duration'] for section in edited['sections']] == [1., 1., 3.]
    assert edited['footage'] == original['footage']
    assert edited['sections'][1] == original['sections'][1]
    assert edited['sections'][0]['effects_rate'] == .35
    assert edited['sections'][2]['effects_rate'] == .5
    assert edited['sections'][0]['video_rate'] == (.4 if mode == 'video' else .8)
    assert edited['sections'][2].get('video_rate', 1.) == (.5 if mode == 'video' else 1.)
    result = compile_composition(edited)
    assert mapped_time(result['time_map'], .5, 'video') == pytest.approx(.2 if mode == 'video' else .4)
    assert stretch_sections(edited, ['cut-0', 'cut-2'], .5, mode) == original


@pytest.mark.parametrize('identifiers,factor,mode', [
    ([], 2., 'effects'), (['missing'], 2., 'effects'),
    (['section-1', 'missing'], 2., 'effects'), ('section-1', 2., 'effects'),
    (['section-1'], float('nan'), 'effects'), (['section-1'], float('inf'), 'effects'),
    (['section-1'], True, 'effects'), (['section-1'], '2', 'effects'),
    (['section-1'], 2., 'invalid'),
])
def test_invalid_selection_stretch_does_not_mutate_document(identifiers, factor, mode):
    original = project()
    before = copy.deepcopy(original)
    with pytest.raises(ValueError): stretch_sections(original, identifiers, factor, mode)
    assert original == before
