import copy
import subprocess

import numpy as np
import pytest
from PIL import Image

from synth import default_synth_preset
from synth_composition import compile_composition, composition_from_sequence, load_composition, mixed_media_composition, normalize_composition, save_composition
from synth_effects import effect_preset
from synth_master import DEFAULT_MASTER, apply_master, normalize_master
from synth_media import export_synth_video
from synth_sequence import load_sequence, normalize_sequence, render_sequence_frame, save_sequence


def test_master_neutral_and_bypass_are_exact_and_do_not_mutate_pixels():
    image = Image.fromarray(np.random.default_rng(25).integers(0, 256, (24, 32, 3), dtype=np.uint8))
    before = image.tobytes()
    assert apply_master(image) is image
    assert apply_master(image, DEFAULT_MASTER) is image
    assert apply_master(image, dict(brightness=.5, saturation=0., enabled=False)) is image
    assert image.tobytes() == before


def test_master_controls_have_predictable_color_and_brightness_endpoints():
    image = Image.fromarray(np.array([[[255, 0, 0], [0, 255, 0], [0, 0, 255], [64, 64, 64]]], dtype=np.uint8))
    gray = np.asarray(apply_master(image, {'saturation': 0.}))
    assert gray.tolist() == [[[54, 54, 54], [182, 182, 182], [18, 18, 18], [64, 64, 64]]]
    assert np.asarray(apply_master(image, {'brightness': 1.})).min() == 255
    assert np.asarray(apply_master(image, {'brightness': -1.})).max() == 0
    assert np.asarray(apply_master(image, {'contrast': 0.})).tolist() == [[[128] * 3] * 4]
    assert np.asarray(apply_master(image, {'brightness': .2}))[0, 3].tolist() == [115] * 3
    assert np.asarray(apply_master(image, {'contrast': 3.}))[0, 3].tolist() == [0] * 3


@pytest.mark.parametrize('transition', ['cut', 'morph', 'flash', 'sweep'])
def test_master_treats_both_sections_after_transitions_and_background(transition):
    project = mixed_media_composition()
    sequence = compile_composition(project)
    sequence['cues'][1].update(transition=transition, duration=.8, intensity=.65)
    sequence['field'].update(cloud_strength=.15, cloud_start=0., cloud_late_start=20.)
    graded = copy.deepcopy(sequence)
    graded['master'].update(brightness=.08, contrast=1.2, saturation=0.)
    for time in (1.4, sequence['cues'][1]['time'] + .2):
        original = render_sequence_frame(sequence, time, (128, 128))
        output = render_sequence_frame(graded, time, (128, 128))
        assert output.tobytes() == apply_master(original, graded['master']).tobytes()
        assert output.tobytes() != original.tobytes()
        pixels = np.asarray(output)
        assert np.array_equal(pixels[..., 0], pixels[..., 1])
        assert np.array_equal(pixels[..., 0], pixels[..., 2])
    assert sequence['master'] == DEFAULT_MASTER


def test_master_preserves_low_res_preview_texture_in_the_full_canvas():
    project = mixed_media_composition()
    project['canvas'].update(width=1080, height=1920)
    project['effects']['low_res'] = effect_preset('low_res')
    project['master'].update(brightness=.03, contrast=1.15, saturation=.4)
    sequence = compile_composition(project)
    preview = render_sequence_frame(sequence, 1.4, (202, 360))
    full = render_sequence_frame(sequence, 1.4, (1080, 1920))
    assert full.tobytes() == preview.resize(full.size, Image.Resampling.BILINEAR).tobytes()


def test_master_roundtrip_compiler_import_and_legacy_compatibility(tmp_path):
    project = mixed_media_composition(); legacy = copy.deepcopy(project); legacy.pop('master')
    assert normalize_composition(legacy) == project
    before = copy.deepcopy(project)
    project['master'].update(brightness=.12, contrast=1.3, saturation=.5)
    path = tmp_path / 'composition.json'; save_composition(path, project)
    assert load_composition(path) == project
    sequence = compile_composition(project)
    assert project['source'] == before['source'] and project['sections'] == before['sections']
    path = tmp_path / 'detailed.json'; save_sequence(path, sequence)
    assert load_sequence(path) == sequence
    imported = composition_from_sequence(sequence)
    assert imported['master'] == sequence['master']
    # Wrapping a graded sequence in the composer must not apply master twice.
    assert render_sequence_frame(compile_composition(imported), 1.4, (120, 120)).tobytes() == render_sequence_frame(sequence, 1.4, (120, 120)).tobytes()


def test_actual_export_includes_master_pixels(tmp_path):
    project = mixed_media_composition(); project['canvas'].update(width=160, height=200)
    project['master'].update(saturation=0., brightness=.15)
    sequence = compile_composition(project)
    path = tmp_path / 'master.mp4'
    export_synth_video(default_synth_preset(), path, start=20, count=2, sequence=sequence)
    decoded = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(path), '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'])
    frames = np.frombuffer(decoded, dtype=np.uint8).reshape(2, 200, 160, 3)
    for index, frame in enumerate(frames):
        expected = np.asarray(render_sequence_frame(sequence, (20 + index) / 15, (160, 200)), dtype=float)
        assert np.abs(frame.astype(float) - expected).mean() < 3
        assert np.ptp(frame.astype(int), axis=-1).max() <= 1


@pytest.mark.parametrize('value', [[], {'brightness': True}, {'brightness': float('nan')}, {'contrast': -1}, {'saturation': 4}, {'enabled': 1}, {'unknown': .2}])
def test_invalid_master_is_rejected_in_compositions_and_sequences(value):
    project = mixed_media_composition()
    with pytest.raises(ValueError): normalize_master(value)
    with pytest.raises(ValueError): normalize_composition(dict(project, master=value))
    with pytest.raises(ValueError): normalize_sequence(dict(project['source'], master=value))
