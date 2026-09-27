import copy
import json
import subprocess

import pytest
from PIL import Image

from synth import default_synth_preset, render_synth_frame
from synth_canvas import format_canvas, preview_size
from synth_composition import compile_composition, mixed_media_composition
from synth_effects import effect_preset
from synth_media import export_synth_video
from synth_sequence import render_sequence_frame


def test_standalone_matches_the_actual_preview_raster_and_bypasses_exactly():
    preset = default_synth_preset()
    module = next(m for m in preset['modules'] if m['id'] == 'low_res')
    assert not module['enabled']
    native = render_synth_frame(preset, time_seconds=.4)
    preview = render_synth_frame(preset, time_seconds=.4, size=(360, 288))
    module['enabled'] = True
    assert render_synth_frame(preset, time_seconds=.4).tobytes() == preview.resize(native.size, Image.Resampling.BILINEAR).tobytes()
    assert render_synth_frame(preset, time_seconds=.4, size=preview.size).tobytes() == preview.tobytes()
    module['params']['sampling'] = 1
    assert render_synth_frame(preset, time_seconds=.4).tobytes() == preview.resize(native.size, Image.Resampling.NEAREST).tobytes()
    module['params']['resolution'] = 720
    assert render_synth_frame(preset, time_seconds=.4).tobytes() == native.tobytes()
    module['params']['resolution'] = 180
    assert render_synth_frame(preset, time_seconds=.4).tobytes() != native.tobytes()
    module['enabled'] = False
    assert render_synth_frame(preset, time_seconds=.4).tobytes() == native.tobytes()


@pytest.mark.parametrize('format_id', ['square', 'stories', 'wide'])
def test_preview_and_export_use_the_same_canvas_rounded_working_raster(format_id):
    project = mixed_media_composition(); project['canvas'] = format_canvas(format_id)
    size = preview_size(project['canvas'], 360)
    original = copy.deepcopy(project)
    preview = render_sequence_frame(compile_composition(project), 1.6, size)
    project['effects']['low_res'] = effect_preset('low_res')
    sequence = compile_composition(project)
    # All proxy sizes share one raster, including those smaller than the effect.
    for output in (size, preview_size(project['canvas'], 180), preview_size(project['canvas'], 720), preview_size(project['canvas'], None)):
        actual = render_sequence_frame(sequence, 1.6, output)
        assert actual.size == output
        assert actual.tobytes() == preview.resize(output, Image.Resampling.BILINEAR).tobytes()
    assert project['source'] == original['source']
    assert project['sections'] == original['sections']


@pytest.mark.parametrize('transition', ['morph', 'flash', 'sweep'])
def test_sequence_transitions_and_field_noise_are_finished_before_enlarging(transition):
    project = mixed_media_composition()
    raw = compile_composition(project)
    project['effects']['low_res'] = effect_preset('low_res')
    finished = compile_composition(project)
    for sequence in (raw, finished):
        sequence['cues'][1].update(transition=transition, duration=.8, intensity=.6)
        sequence['field'].update(cloud_strength=.12, cloud_start=0., cloud_late_start=20., valley_start=0., valley_end=10., valley_gain=.8)
    time = raw['cues'][1]['time'] + .2
    preview = render_sequence_frame(raw, time, (360, 360))
    actual = render_sequence_frame(finished, time, (540, 540))
    assert actual.tobytes() == preview.resize(actual.size, Image.Resampling.BILINEAR).tobytes()


def test_section_can_override_and_disable_the_global_resolution():
    project = mixed_media_composition()
    native = compile_composition(project)
    project['effects']['low_res'] = effect_preset('low_res')
    project['sections'][1]['effects']['low_res'] = {'mode': 'off', 'params': {}}
    sequence = compile_composition(project)
    time = sequence['cues'][1]['time'] + 1.
    assert render_sequence_frame(sequence, time, (540, 540)).tobytes() == render_sequence_frame(native, time, (540, 540)).tobytes()
    project['sections'][1]['effects']['low_res'] = effect_preset('low_res', 1)
    sequence = compile_composition(project)
    preview = render_sequence_frame(native, time, (180, 180))
    assert render_sequence_frame(sequence, time, (540, 540)).tobytes() == preview.resize((540, 540), Image.Resampling.BILINEAR).tobytes()


def test_low_resolution_effect_exports_the_full_saved_canvas(tmp_path):
    project = mixed_media_composition(); project['canvas'] = format_canvas('stories')
    project['effects']['low_res'] = effect_preset('low_res')
    sequence = compile_composition(project)
    path = tmp_path / 'full-size-lo-fi.mp4'
    export_synth_video(default_synth_preset(), path, count=2, sequence=sequence)
    stream = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height,nb_frames', '-of', 'json', str(path)], text=True))['streams'][0]
    assert (stream['width'], stream['height'], stream['nb_frames']) == (1080, 1920, '2')
