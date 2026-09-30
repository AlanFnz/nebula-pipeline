"""A section stretch retimes all procedural clocks and optional footage together."""
import copy

import pytest
from PIL import Image

from synth_composition import (blank_composition, compile_composition, composition_from_sequence,
                               load_composition, normalize_composition, reference_composition,
                               save_composition, section_placements, stretch_section)
from synth_retime import mapped_time
from synth_sequence import normalize_sequence, render_sequence_frame
from synth_video import video_composition
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
    monkeypatch.setattr('synth_sequence.render_synth_frame', lambda base, time_seconds, size, **kw:
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
    from synth import default_synth_preset
    from synth_media import export_synth_video
    from synth_video import VideoFrameProvider
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
