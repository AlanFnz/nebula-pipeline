"""Hiding an ink source must not replace its authored clock or clip lengths."""
import copy

import pytest

from synth_composition import compile_composition, load_composition, mixed_media_composition, normalize_composition, save_composition
from synth_sequence import render_sequence_frame
from synth_shared_timing import edit_shared_timing


def bypass(project, location, enabled):
    targets = [project] if location == 'global' else project['sections']
    for target in targets:
        entry = target['effects'].setdefault('ink_bloom', {'mode': 'recipe', 'params': {}})
        if enabled:
            entry['bypassed'] = True
        else:
            entry.pop('bypassed', None)


@pytest.mark.parametrize('location', ['global', 'sections'])
def test_bypassed_source_preserves_partial_shared_timing_through_save_and_resume(tmp_path, location):
    project = mixed_media_composition()
    project['ink_timing'] = {'ink_bloom.unfold_seconds': .45}
    original = normalize_composition(project)
    hidden = copy.deepcopy(project); bypass(hidden, location, True)
    hidden = normalize_composition(hidden)
    assert hidden['ink_timing'] == original['ink_timing']
    assert [s['duration'] for s in hidden['sections']] == [s['duration'] for s in original['sections']]
    path = tmp_path / 'bypassed.json'; save_composition(path, hidden)
    restored = load_composition(path)
    assert restored == hidden
    bypass(restored, location, False)
    before, after = compile_composition(original), compile_composition(restored)
    for time in (.2, 1.4, 4.6):
        assert render_sequence_frame(before, time, (96, 96)).tobytes() == render_sequence_frame(after, time, (96, 96)).tobytes()


@pytest.mark.parametrize('location', ['global', 'sections'])
def test_editing_shared_timing_while_bypassed_keeps_the_same_cycle_resize(location):
    original = mixed_media_composition()
    edit_shared_timing(original, 'ink_bloom.unfold_seconds', .4)
    hidden = copy.deepcopy(original); bypass(hidden, location, True)
    edit_shared_timing(original, 'ink_bloom.folded_seconds', 1.2)
    edit_shared_timing(hidden, 'ink_bloom.folded_seconds', 1.2)
    assert hidden['ink_timing'] == original['ink_timing']
    assert [s['duration'] for s in hidden['sections']] == [s['duration'] for s in original['sections']]
    assert hidden['source'] == original['source']
