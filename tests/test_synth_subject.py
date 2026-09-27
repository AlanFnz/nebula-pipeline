import copy

import pytest

from synth_composition import (compile_composition, load_composition, mixed_media_composition,
                               reference_composition, save_composition, section_ranges)
from synth_effects import describe_effects
from synth_sequence import render_sequence_frame
from synth_subject import active_subjects, restore_subject, scope_states, select_subject


@pytest.mark.parametrize('kind,expected', [('ink', 'ink_bloom'), ('particles', 'particles'), ('signal', 'forms'), ('none', None)])
def test_replacing_object_changes_only_sources_and_preserves_arrangement(kind, expected):
    project = mixed_media_composition(); original = copy.deepcopy(project)
    changed = select_subject(project, kind)
    summary = describe_effects(scope_states(changed))
    if expected: assert summary[expected]['active']
    assert active_subjects(summary) == (() if kind == 'none' else (kind,))
    assert summary['print_surface']['active'] and summary['frame_jitter']['active']
    for key in ('source', 'canvas', 'master', 'ink_timing', 'phrases'):
        assert changed[key] == project[key]
    assert section_ranges(changed) == section_ranges(project)
    assert project == original


def test_switching_back_to_authored_signal_restores_animated_source_and_exact_pixels():
    project = reference_composition(refined=True)
    changed = select_subject(select_subject(project, 'particles'), 'signal')
    summary = describe_effects(scope_states(changed))
    assert summary['forms']['intermittent'] and summary['rays']['intermittent']
    before, after = compile_composition(project), compile_composition(changed)
    for time in (0., 3.6, 6.2, 11.6):
        assert render_sequence_frame(before, time, (120, 96)).tobytes() == render_sequence_frame(after, time, (120, 96)).tobytes()


def test_switch_keeps_artwork_parameters_and_roundtrips_through_saved_detailed_sequence(tmp_path):
    project = mixed_media_composition()
    project['effects']['ink_bloom'] = {'mode': 'recipe', 'params': {'ink_bloom.shape': 4, 'ink_bloom.sides': 5, 'ink_bloom.shape_width': .7}}
    original = compile_composition(project)
    changed = select_subject(project, 'particles')
    assert changed['effects']['particles']['params']['particles.attractor'] == 4
    path = tmp_path / 'objects.json'; save_composition(path, changed)
    restored = restore_subject(load_composition(path))
    assert restored['effects']['ink_bloom']['params'] == project['effects']['ink_bloom']['params']
    assert render_sequence_frame(compile_composition(restored), 1.3, (160, 160)).tobytes() == render_sequence_frame(original, 1.3, (160, 160)).tobytes()


def test_section_object_and_global_replacement_respect_scope_and_keep_local_parameters():
    project = mixed_media_composition()
    local = select_subject(project, 'particles', 1)
    assert active_subjects(describe_effects(scope_states(local, 0))) == ('ink',)
    assert active_subjects(describe_effects(scope_states(local, 1))) == ('particles',)
    local['sections'][1]['effects']['particles']['params']['particles.scale'] = .65
    global_change = select_subject(local, 'signal')
    for index in (0, 1): assert active_subjects(describe_effects(scope_states(global_change, index))) == ('signal',)
    assert global_change['sections'][1]['effects']['particles']['params']['particles.scale'] == .65
    assert section_ranges(global_change) == section_ranges(project)


def test_invalid_object_type_is_rejected():
    with pytest.raises(ValueError): select_subject(mixed_media_composition(), 'unknown')
