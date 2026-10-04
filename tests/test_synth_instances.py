import copy
import json

import numpy as np
import pytest

from synth import MODULE_BY_ID, render_synth_frame
from synth_automation import target_parameter
from synth_composition import (blank_composition, compile_composition,
                               composition_from_sequence, normalize_composition)
from synth_effects import effect_preset, describe_effects
from synth_effect_discovery import effect_candidate
from synth_sequence import resolve_sequence_frame, render_sequence_frame
from synth_instances import instance_base, document_instance_ids
from test_synth_video import clip


def gesture(path='tape@2.pull'):
    return dict(id='pull', path=path, start_fraction=.4, attack_fraction=.015,
                hold_fraction=0., recovery_fraction=.085, amount=.3,
                enabled=True, easing='smooth')


def piece():
    p = blank_composition(); p['sections'][0]['duration'] = 10.
    p['canvas'] = dict(width=160, height=120, framing='native')
    p['effects']['forms'] = effect_preset('forms', 0)
    p['effects']['tape'] = effect_preset('tape', 1)
    return normalize_composition(p)


def frame(sequence, seconds):
    return np.asarray(render_sequence_frame(sequence, time_seconds=seconds, size=(160,120)))


def test_neutral_instance_preserves_render_and_original_module_order_then_animates_independently():
    p = piece(); original = compile_composition(p)
    p['effects']['tape@2'] = effect_preset('tape@2', 3)
    neutral = compile_composition(p)
    for seconds in (0., 4., 4.2, 5., 9.9):
        assert np.array_equal(frame(original, seconds), frame(neutral, seconds))
    p['sections'][0]['automations'] = [gesture()]
    animated = compile_composition(p)
    before = resolve_sequence_frame(original, 4.15)[-1]
    during = resolve_sequence_frame(animated, 4.15)[-1]
    assert during['modules'][:-1] == before['modules']
    assert during['modules'][-1]['id'] == 'tape@2'
    assert during['modules'][-1]['params']['pull'] == pytest.approx(.3)
    assert not np.array_equal(frame(original, 4.2), frame(animated, 4.2))
    for seconds in (0., 3.9, 4., 5., 9.9):
        assert np.array_equal(frame(original, seconds), frame(animated, seconds))


def test_distinct_automation_targets_and_bypass_only_affect_their_instance():
    p = piece(); p['effects']['tape@2'] = effect_preset('tape@2', 3)
    p['sections'][0]['automations'] = [gesture(), dict(gesture('tape.pull'), id='original', amount=-.1)]
    seq = compile_composition(p)
    modules = {m['id']: m for m in resolve_sequence_frame(seq, 4.15)[-1]['modules']}
    assert modules['tape']['params']['pull'] == pytest.approx(-.1)
    assert modules['tape@2']['params']['pull'] == pytest.approx(.3)
    p['effects']['tape@2']['bypassed'] = True
    modules = {m['id']: m for m in resolve_sequence_frame(compile_composition(p), 4.15)[-1]['modules']}
    assert modules['tape']['enabled'] and not modules['tape@2']['enabled']
    assert modules['tape@2']['params']['pull'] == 0.


def test_save_detailed_roundtrip_and_loop_retime_keep_instance_targets():
    p = piece(); p['effects']['tape@2'] = effect_preset('tape@2', 3)
    p['sections'][0]['automations'] = [gesture()]
    p['sections'][0].update(duration=20., loops=2)
    seq = compile_composition(normalize_composition(json.loads(json.dumps(p))))
    assert [e['start'] for e in seq['automations']] == [8.,28.]
    assert seq['automations'][0]['attack'] == .3
    detailed = compile_composition(composition_from_sequence(seq))
    assert document_instance_ids(composition_from_sequence(seq)) == ['tape@2']
    for seconds in (0., 8.3, 10., 28.3):
        assert np.array_equal(frame(seq, seconds), frame(detailed, seconds))


def test_section_scope_disabled_slots_and_stable_order_across_morph():
    p = piece(); second = copy.deepcopy(p['sections'][0]); second['id'] = 'second'
    p['sections'].append(second)
    second['effects']['tape@3'] = effect_preset('tape@3', 3)
    p['sections'][0]['effects']['tape@2'] = effect_preset('tape@2', 3)
    seq = compile_composition(p)
    for seconds, flags in ((1., (True,False)), (11., (False,True))):
        modules = resolve_sequence_frame(seq, seconds)[-1]['modules']
        assert [m['id'] for m in modules[-2:]] == ['tape@2', 'tape@3']
        assert tuple(m['enabled'] for m in modules[-2:]) == flags
    summary = describe_effects(list(seq['states'].values()))
    assert summary['tape@2']['intermittent']
    assert summary['tape@3']['intermittent']
    from synth_sequence import _interpolate_presets
    first = resolve_sequence_frame(seq, 1.)[-1]
    second = resolve_sequence_frame(seq, 11.)[-1]
    mid = _interpolate_presets(first, second, .75)
    assert [m['id'] for m in mid['modules'][-2:]] == ['tape@2', 'tape@3']
    assert tuple(m['enabled'] for m in mid['modules'][-2:]) == (False, True)


def test_instance_preset_audition_changes_only_requested_entry():
    p = piece(); p['effects']['tape@2'] = effect_preset('tape@2', 3)
    updated = effect_candidate(p, None, 'tape@2', 'replace', 1)
    assert updated['effects']['tape'] == p['effects']['tape']
    assert updated['effects']['tape@2']['params']['tape@2.tracking'] == .11
    updated['effects']['tape@2'] = p['effects']['tape@2']
    assert updated == p


def test_video_pixels_support_extra_pass_without_requiring_generator():
    p = piece(); p['effects']['tape@2'] = effect_preset('tape@2', 3)
    p['sections'][0]['automations'] = [gesture()]
    preset = resolve_sequence_frame(compile_composition(p), 4.2)[-1]
    from synth_video import VIDEO_MODULES
    for m in preset['modules']:
        if m['id'] not in VIDEO_MODULES and not instance_base(m['id']): m['enabled'] = False
    from PIL import Image
    source = Image.fromarray(np.tile(np.arange(160,dtype=np.uint8)[None,:,None], (120,1,3)))
    result = render_synth_frame(preset, time_seconds=4.2, size=(160,120), source_image=source)
    assert result.size == (160,120)


def test_registry_is_bounded_and_does_not_mutate_the_legacy_catalog():
    before = tuple(MODULE_BY_ID)
    assert MODULE_BY_ID['tape@64'].id == 'tape@64'
    assert tuple(MODULE_BY_ID) == before
    for identifier in ('tape@0','tape@1','tape@02','tape@65','raster@2'):
        assert instance_base(identifier) is None
        with pytest.raises(ValueError):
            normalize_composition(dict(piece(), effects={identifier: dict(mode='on', params={})}))
    assert target_parameter('tape@2.pull') == target_parameter('tape.pull')
    with pytest.raises(ValueError): target_parameter('tape@2.rate')


def test_imported_video_export_renders_both_passes_and_preserves_frames_outside_gesture(clip, tmp_path):
    import subprocess
    from synth import default_synth_preset
    from synth_video import video_composition, VideoFrameProvider, inspect_video
    from synth_media import export_synth_video
    p = video_composition(clip)
    p['fps'] = 15; p['sections'][0]['duration'] = 2.
    p['effects']['tape'] = effect_preset('tape', 1)
    original = compile_composition(p)
    p['effects']['tape@2'] = effect_preset('tape@2', 3)
    p['sections'][0]['automations'] = [dict(gesture(), amount=.7)]
    seq = compile_composition(p)
    with VideoFrameProvider() as provider:
        for t in (0., .5, 1., 1.5):
            assert np.array_equal(render_sequence_frame(seq,t,(120,80),provider), render_sequence_frame(original,t,(120,80),provider))
        during = np.asarray(render_sequence_frame(seq,13/15,(120,80),provider), dtype=float)
        before = np.asarray(render_sequence_frame(original,13/15,(120,80),provider), dtype=float)
        assert not np.array_equal(during, before)
    output = export_synth_video(default_synth_preset(), tmp_path/'two-passes.mp4', sequence=seq, size=(120,80))
    info = inspect_video(output)
    assert info['fps'] == 15 and abs(info['duration']-2.) < 1/15
    decoded = subprocess.run(['ffmpeg','-v','error','-i',str(output),'-f','rawvideo','-pix_fmt','rgb24','pipe:1'],check=True,capture_output=True).stdout
    frames = np.frombuffer(decoded, np.uint8).reshape(-1,80,120,3)
    assert len(frames) == 30
    assert np.abs(frames[13].astype(float)-during).mean() < np.abs(frames[13].astype(float)-before).mean()
