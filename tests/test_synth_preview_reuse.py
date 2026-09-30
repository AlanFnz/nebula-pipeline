"""Conservative frame retention agrees with fresh RGB at absolute cue times."""
import copy
import os
from pathlib import Path
import pytest
from PySide6.QtCore import Qt
from synth_composition import reference_composition, normalize_composition, compile_composition
from synth_sequence import reference_sequence, normalize_sequence, render_sequence_frame
from synth_effects import effect_preset
from synth_preview import RenderValidity, retained_frame_predicate, _file_fingerprint
from test_synth_composer_ui import window, wait_until


def transition_document():
    project = reference_composition(refined=True)
    source = reference_sequence()
    source.update(render_version=2, duration=1.2, fps=20,
                  states={key: {'preset': 'Reference blinds', 'enabled': ['slab', 'raster'],
                                'overrides': {'slab.x': value}} for key, value in zip('abc', (.3, .5, .7))},
                  cues=[{'time': 0., 'state': 'a', 'transition': 'cut'},
                        {'time': .4, 'state': 'b', 'transition': 'morph', 'duration': .2},
                        {'time': .8, 'state': 'c', 'transition': 'morph', 'duration': .2}])
    project.update(source=normalize_sequence(source), render_version=2, fps=20, effects={},
                   phrases={key: {'name': key, 'start': round(i*.4, 2), 'end': round((i+1)*.4, 2)} for i, key in enumerate('abc')})
    base = project['sections'][0]
    project['sections'] = [dict(copy.deepcopy(base), id=f'section-{i}', phrase=key, duration=.4) for i, key in enumerate('abc')]
    project['timeline_loops'] = [{'sections': [s['id'] for s in project['sections']], 'loops': 2}]
    return normalize_composition(project)


def local_edit(project):
    edited = copy.deepcopy(project)
    entry = effect_preset('raster'); entry['params']['raster.grain'] = .3
    edited['sections'][1]['effects']['raster'] = entry
    return normalize_composition(edited)


def validity(project, identity, context=((120, 90), False, ())):
    return RenderValidity.capture(identity, project, compile_composition(project), None, context)


def test_local_reuse_invalidates_both_repeats_and_following_morph_then_matches_fresh_pixels():
    before = transition_document(); after = local_edit(before); identity = object()
    old, new = validity(before, identity), validity(after, identity)
    retain = retained_frame_predicate(old, new)
    assert retain is not None
    invalid = {frame for frame in range(48) if not retain(frame)}
    assert invalid == set(range(8, 20)) | set(range(32, 44))
    changed_pixels = []
    for frame in range(48):
        first = render_sequence_frame(old.sequence, frame/20, (120, 90)).tobytes()
        second = render_sequence_frame(new.sequence, frame/20, (120, 90)).tobytes()
        if retain(frame): assert first == second
        elif first != second: changed_pixels.append(frame)
    assert 16 in changed_pixels and 40 in changed_pixels  # Morph into each following third-section occurrence.
    assert retain(20) and retain(44)  # Exact completed-morph boundary.


@pytest.mark.parametrize('change', ['master', 'canvas', 'seed', 'renderer', 'duration', 'retime', 'reorder', 'loop', 'source', 'unknown'])
def test_unclassified_or_global_changes_clear_all(change):
    before = transition_document(); after = copy.deepcopy(before); identity = object()
    if change == 'master': after['master']['brightness'] = .5
    elif change == 'canvas': after['canvas']['width'] += 64
    elif change == 'seed': after['seed'] += 1
    elif change == 'renderer': after['render_version'] = 1; after['source']['render_version'] = 1
    elif change == 'duration': after['sections'][0]['duration'] += .1
    elif change == 'retime': after['sections'][0]['effects_rate'] = .5
    elif change == 'reorder': after['sections'].reverse()
    elif change == 'loop': after['timeline_loops'][0]['loops'] = 3
    elif change == 'source': after['source']['states']['a']['overrides']['slab.x'] = .1
    else: after['sections'][0]['variation'] += 1
    assert retained_frame_predicate(validity(before, identity), validity(after, identity)) is None


@pytest.mark.parametrize('context', [((240, 180), False, ()), ((120, 90), True, ()), ((120, 90), False, ('source changed',))])
def test_dimensions_bypass_or_media_identity_clear(context):
    project = transition_document(); identity = object()
    assert retained_frame_predicate(validity(project, identity), validity(project, identity, context)) is None
    assert retained_frame_predicate(validity(project, identity), validity(project, object())) is None


def test_proxy_fingerprint_ignores_touch_but_detects_middle_overwrite(tmp_path):
    path = tmp_path/'proxy.mkv'; path.write_bytes(b'a'*300000)
    original = _file_fingerprint(path, content=True)
    os.utime(path, None)
    assert _file_fingerprint(path, content=True) == original
    with path.open('r+b') as stream:
        stream.seek(150000); stream.write(b'b')
    assert _file_fingerprint(path, content=True) != original
    path.unlink()
    assert _file_fingerprint(path, content=True)[-1] == 'unavailable'


def test_window_retains_unaffected_rgb_and_rejects_old_generation_after_edit_and_undo(window, monkeypatch):
    window.auto_prepare.setChecked(False)
    monkeypatch.setattr(window, 'preview_size', lambda: (120, 90))
    window.set_composition(transition_document())
    wait_until(lambda: not window.render_running and not window.render_queued)
    window.prepare_playback()
    wait_until(lambda: not window.preparation_explicit and window.prepare_job is None)
    assert window.preview_frames.complete(48)
    original = dict(window.preview_frames.items); old_generation = window.settings_generation
    window.composer.select_section(1)
    window.composer.change_effect('raster', local_edit(window.composition)['sections'][1]['effects']['raster'], 'effect-param')
    assert window.settings_generation > old_generation
    assert set(window.preview_frames.items) == set(range(48)) - set(range(8, 20)) - set(range(32, 44))
    for frame, packet in window.preview_frames.items.items():
        assert packet is original[frame]
        assert packet[1] == render_sequence_frame(window.sequence, frame/20, packet[0]).tobytes()
    before = dict(window.preview_frames.items)
    window.frame_ready((old_generation, 999999, .4, (1, 1), b'old', .01))
    assert dict(window.preview_frames.items) == before
    edit_generation = window.settings_generation
    window.undo_composition()
    window.frame_ready((edit_generation, 999999, .4, (1, 1), b'old', .01))
    assert all(packet[1] != b'old' for packet in window.preview_frames.items.values())
    assert not window.has_unsaved_changes()
    window.preview_scope.setCurrentIndex(1)
    cache = dict(window.preview_frames.items); generation = window.settings_generation
    window.viewer.set_zoom(1.2)
    window.section_timeline.select_at(2, Qt.KeyboardModifier.MetaModifier)
    assert window.settings_generation == generation and dict(window.preview_frames.items) == cache


def test_actual_source_replacement_clears_cache_and_rejects_inflight_packet(window, tmp_path):
    window.auto_prepare.setChecked(False)
    wait_until(lambda: not window.render_running and not window.render_queued)
    source = tmp_path/'source.mov'; source.write_bytes(b'first source')
    window.sequence['footage'] = {'path': str(source), 'identity': {'size': source.stat().st_size, 'mtime_ns': source.stat().st_mtime_ns}, 'sample_fps': 12}
    window.preview_validity = window.capture_preview_validity()
    window.preview_frames.put(0, ((1, 1), b'old'))
    generation = window.settings_generation
    replacement = tmp_path/'replacement.mov'; replacement.write_bytes(b'newer source'); os.replace(replacement, source)
    window.frame_ready((generation, 999999, 0., (1, 1), b'old', .01))
    assert window.settings_generation > generation and not window.preview_frames.items
    window.preview_debounce.stop(); window.render_queued = False
