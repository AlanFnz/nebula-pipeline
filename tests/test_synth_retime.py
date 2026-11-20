"""A clip stretch retimes all procedural clocks and optional footage together."""
import copy

import pytest
from PIL import Image

from nebula.documents.synth_composition import (blank_composition, compile_composition, composition_from_sequence,
                               load_composition, normalize_composition, reference_composition,
                               save_composition, section_placements, stretch_section)
from nebula.documents.synth_retime import mapped_time
from nebula.documents.synth_sequence import normalize_sequence, render_sequence_frame
from nebula.sources.synth_video import video_composition
from test_synth_video import clip


def pixels(sequence, time):
    return render_sequence_frame(sequence, round(time, 10), (96, 72)).tobytes()


def test_stretch_preserves_effects_transitions_and_following_section_phase(tmp_path):
    project = reference_composition(refined=True)
    before = copy.deepcopy(project)
    original = compile_composition(project)
    stretched = stretch_section(project, 'section-2', 6.)
    result = compile_composition(stretched)
    assert project == before
    assert result['duration'] == 18.
    assert result['states'] == original['states']
    assert stretched['sections'][1]['effects_rate'] == .5
    assert 'video_rate' not in stretched['sections'][1]
    for time in (0., 2.4, 5.2):
        assert pixels(result, time) == pixels(original, time)
    for offset in (0., .08, .32, 1.08, 2.16, 2.96):
        assert pixels(result, 5.24 + 2 * offset) == pixels(original, 5.24 + offset)
    for time in (8.24, 9.6, 10.4, 12.8, 14.96):
        assert pixels(result, time + 3) == pixels(original, time)
    path = tmp_path / 'stretched.json'
    save_composition(path, stretched)
    assert compile_composition(load_composition(path)) == result
    # The detailed editor/import route must retain the time map too.
    imported = compile_composition(composition_from_sequence(result))
    for time in (2.4, 6.8, 12., 17.2):
        assert pixels(imported, time) == pixels(result, time)
    restored = stretch_section(stretched, 'section-2', 3.)
    assert 'time_map' not in compile_composition(restored)
    assert normalize_composition(restored) == normalize_composition(before)


def test_compress_and_stretch_again_uses_current_scale():
    project = reference_composition()
    original = compile_composition(project)
    compressed = stretch_section(project, 'section-2', 1.52)
    result = compile_composition(compressed)
    assert result['time_map'][1]['effects_rate'] == pytest.approx(3 / 1.52)
    assert mapped_time(result['time_map'], 6.76) == pytest.approx(8.24)
    stretched = stretch_section(compressed, 'section-2', 6.)
    assert stretched['sections'][1]['effects_rate'] == pytest.approx(.5)
    assert pixels(compile_composition(stretched), 7.4) == pixels(original, 6.32)


def test_loops_retime_all_occurrences_and_clamp_whole_arrangement():
    project = reference_composition()
    project['sections'][1]['loops'] = 3
    project['timeline_loops'] = [{'sections': ['section-1', 'section-2'], 'loops': 4}]
    original = compile_composition(project)
    stretched = stretch_section(project, 'section-2', 6.)
    result = compile_composition(stretched)
    assert result['duration'] == original['duration'] + 36
    assert mapped_time(result['time_map'], result['duration']) == pytest.approx(original['duration'])
    ranges = section_placements(stretched)
    assert [end - start for index, start, end, _ in ranges if index == 1] == pytest.approx([18] * 4)
    stretched = stretch_section(project, 'section-2', 300)
    assert section_placements(stretched)[-1][2] <= 3600
    assert section_placements(stretched)[-1][2] > 3599


def test_one_frame_and_no_op_are_valid():
    project = blank_composition()
    result = stretch_section(project, 'section-1', 0)
    sequence = compile_composition(result)
    assert sequence['duration'] == 1 / project['fps']
    render_sequence_frame(sequence, 0, (32, 24))
    assert stretch_section(project, 'section-1', project['sections'][0]['duration']) == normalize_composition(project)


def test_separate_video_and_effect_clocks_feed_frames_masks_and_bypass(clip, monkeypatch):
    project = video_composition(clip)
    project['effects']['subject_cutout'] = {'mode': 'on', 'params': {'subject_cutout.mix': 1.}}
    effect_times = []
    monkeypatch.setattr('nebula.documents.synth_sequence.render_synth_frame', lambda base, time_seconds, size, **kw:
                        effect_times.append(time_seconds) or Image.new('RGB', size))
    class Provider:
        def __init__(self): self.frames = []; self.masks = []
        def frame(self, footage, time, edge):
            self.frames.append(time); return Image.new('RGB', (128, 96))
        def mask(self, footage, time, base, mode, **kwargs):
            self.masks.append(time); return Image.new('L', (128, 96))
    identifier = project['sections'][0]['id']
    for mode, expected in [('effects', .5), ('video', .25)]:
        sequence = compile_composition(stretch_section(project, identifier, 2., mode))
        provider = Provider()
        render_sequence_frame(sequence, .5, (128, 96), provider)
        assert effect_times[-1] == .25
        assert provider.frames == [expected] and provider.masks == [expected]
        render_sequence_frame(sequence, .5, (128, 96), provider, bypass=True)
        assert provider.frames[-1] == expected
    # Changing modes affects only the new resize; existing source speed survives.
    together = stretch_section(project, identifier, 2., 'video')
    effects_only = stretch_section(together, identifier, 4., 'effects')
    assert effects_only['sections'][0]['effects_rate'] == .25
    assert effects_only['sections'][0]['video_rate'] == .5


def test_nested_detailed_copy_can_be_stretched_again():
    original = compile_composition(reference_composition())
    first = compile_composition(stretch_section(reference_composition(), 'section-2', 6.))
    imported = composition_from_sequence(first)
    second = compile_composition(stretch_section(imported, 'section-1', 36.))
    for time in (1.6, 6.32, 7.96, 9.6, 14.8):
        first_time = time if time < 5.24 else 5.24 + 2 * (time - 5.24) if time < 8.24 else time + 3
        assert pixels(second, first_time * 2) == pixels(original, time)


@pytest.mark.parametrize('bad', [float('nan'), float('inf'), 0, -1, True, '2'])
def test_invalid_clock_rates_rejected(bad):
    project = reference_composition()
    project['sections'][0]['effects_rate'] = bad
    with pytest.raises(ValueError): normalize_composition(project)


@pytest.mark.parametrize('change', [
    lambda m: m[0].update(start=.1),
    lambda m: m[-1].update(end=200),
    lambda m: m[0].update(effects_rate=0),
    lambda m: m[0].update(video_start=float('nan')),
    lambda m: m[1].update(start=m[0]['end'] + .1),
])
def test_invalid_sequence_maps_rejected(change):
    sequence = compile_composition(stretch_section(reference_composition(), 'section-2', 6.))
    change(sequence['time_map'])
    with pytest.raises(ValueError): normalize_sequence(sequence)


def test_legacy_subframe_sequence_still_loads():
    sequence = compile_composition(blank_composition())
    sequence.update(duration=.1, fps=1)
    assert normalize_sequence(sequence)['duration'] == .1


@pytest.mark.parametrize('mode,has_late_audio', [('effects', False), ('video', True)])
def test_end_to_end_export_keeps_video_and_audio_clock_in_sync(clip, tmp_path, mode, has_late_audio):
    import json
    import subprocess
    import numpy as np
    from nebula.render.synth import default_synth_preset
    from nebula.documents.synth_media import export_synth_video
    from nebula.sources.synth_video import VideoFrameProvider
    project = video_composition(clip)
    project['footage'].update(audio='keep', end_mode='hold')
    project = stretch_section(project, project['sections'][0]['id'], 2., mode)
    sequence = compile_composition(project)
    output = tmp_path / f'{mode}.mp4'
    export_synth_video(default_synth_preset(), output, sequence=sequence, size=(128, 96))
    streams = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(output)]))['streams']
    video = next(stream for stream in streams if stream['codec_type'] == 'video')
    assert int(video['nb_frames']) == 24
    assert float(video['duration']) == pytest.approx(2.)
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(output), '-ss', '1.4', '-t', '0.3', '-f', 'f32le', '-ac', '1', '-ar', '48000', '-'])
    rms = float(np.sqrt(np.mean(np.frombuffer(raw, dtype='<f4') ** 2)))
    assert (rms > .01) == has_late_audio
    with VideoFrameProvider() as provider:
        # Before/source uses exactly the clock exported alongside the audio.
        expected = provider.frame(sequence['footage'], .75 if mode == 'video' else 1.5)
        actual = render_sequence_frame(sequence, 1.5, (128, 96), provider, bypass=True)
        assert actual.tobytes() == expected.tobytes()


def test_smart_extension_preserves_authored_frames_and_recovers_optical_pace(tmp_path):
    from nebula.documents.synth_prismatic_recipes import prismatic_composition
    from nebula.documents.synth_sequence import resolve_sequence_frame

    project = prismatic_composition()
    identifier = project['sections'][0]['id']
    before = compile_composition(project)
    extended = stretch_section(project, identifier, 20., 'smart')
    after = compile_composition(extended)
    assert after['cues'][:-1] == before['cues']
    assert 'time_map' not in after
    assert after['cues'][-1]['time'] == 15.
    for t in (0., 5.2, 11.16, 11.6, 14.96, 15.):
        assert pixels(before, t) == pixels(after, t)

    def phase(t):
        base = resolve_sequence_frame(after, t, normalized=True)[-1]
        p = next(m['params'] for m in base['modules'] if m['id'] == 'prismatic_field')
        return (p['color_phase'] + t * base['speed'] * p['color_speed']) % 1.

    assert (phase(15.04) - phase(15.)) % 1 == pytest.approx(.025 * .04, abs=.00001)
    assert (phase(19.) - phase(18.)) % 1 == pytest.approx(.16)
    assert pixels(after, 19.) != pixels(before, 4.)
    path = tmp_path / 'longer.nebula'
    save_composition(path, extended)
    assert compile_composition(load_composition(path)) == after
    detailed = compile_composition(composition_from_sequence(after))
    for t in (15., 15.4, 19.6):
        assert pixels(after, t) == pixels(detailed, t)
    longer = compile_composition(stretch_section(extended, identifier, 26., 'smart'))
    assert longer['cues'] == after['cues']
    assert pixels(after, 19.6) == pixels(longer, 19.6)
    assert stretch_section(extended, identifier, 15., 'smart') == project


def test_smart_extension_retains_cues_and_gesture_seconds_in_each_play():
    from nebula.documents.synth_composition import stretch_sections

    project = reference_composition()
    section = project['sections'][0]
    section['loops'] = 2
    section['automations'] = [dict(id='accent', path='dye_transfer.scale', amount=.1, enabled=True,
                                   easing='smooth', start_fraction=.25, attack_fraction=.25,
                                   hold_fraction=.25, recovery_fraction=.25)]
    original = compile_composition(project)
    extended = stretch_sections(project, [section['id']], 2., 'smart')
    seq = compile_composition(extended)
    old = section['duration']
    for play, (a, b) in enumerate(zip(original['automations'], seq['automations'], strict=True)):
        assert b['start'] == pytest.approx(a['start'] + play * old)
        for stage in ('attack', 'hold', 'recovery'):
            assert a[stage] == pytest.approx(b[stage])
    per_play = [c['time'] for c in original['cues'] if c['time'] < old]
    assert [c['time'] for c in seq['cues'] if c['time'] < 4*old] == pytest.approx(
        per_play + [2*old+t for t in per_play])
    assert 'effects_rate' not in extended['sections'][0]


def test_smart_extension_preserves_global_performance_times_and_fixed_palette():
    from nebula.documents.synth_composition import resize_total_duration
    from nebula.documents.synth_performance import defaults, values_at
    from nebula.documents.synth_prismatic_recipes import prismatic_composition

    project = prismatic_composition()
    perf = defaults()
    perf['tracks'] = {'pace': [[0., 80.], [.5, 90.], [1., 100.]]}
    project['visual_performance'] = perf
    # A user-chosen fixed drift takes precedence over the study's earlier cue.
    for state in project['source']['states'].values():
        state['overrides']['prismatic_field.color_speed'] = .025
    extended = resize_total_duration(project, 20., 'smart')
    assert compile_composition(extended)['cues'] == compile_composition(project)['cues']
    for t in (2., 8., 11., 15.):
        assert values_at(extended['visual_performance'], t, 20.) == pytest.approx(values_at(perf, t, 15.))
