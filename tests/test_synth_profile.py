import copy
import json
import subprocess

import numpy as np
import pytest
from PIL import Image

from synth import MODULE_BY_ID, default_synth_preset, render_synth_frame
from synth_canvas import resize_canvas
from synth_composition import compile_composition, load_composition, profile_signal_composition, save_composition
from synth_effects import describe_effects
from synth_media import export_synth_video
from synth_profile import _neck_dissolve, render_edge_phosphor, render_scan_drag, render_silhouette
from synth_sequence import _state_preset, load_sequence, render_sequence_frame, save_sequence
from synth_subject import active_subjects, restore_subject, scope_states, select_subject


def settings(module, **changes):
    return dict({p.key: p.default for p in MODULE_BY_ID[module].params}, **changes)


def head_preset(**changes):
    preset = default_synth_preset()
    preset.update(width=320, height=240, speed=1., **changes)
    return preset


def test_fixed_mesh_has_no_rotation_or_particle_clock_and_pose_is_editable():
    preset = head_preset(); p = settings('silhouette', scale=.25, center_x=.5, center_y=.4)
    source = np.zeros((240, 320, 3), np.float32); original = source.copy()
    first = render_silhouette(source, p, 0., preset, 1)
    assert np.array_equal(first, render_silhouette(source, p, 123., preset, 50))
    assert not np.array_equal(first, render_silhouette(source, dict(p, yaw=0.), 0., preset, 1))
    assert np.array_equal(source, original)
    assert render_silhouette(source, dict(p, opacity=0.), 0., preset, 1) is source


def test_silhouette_position_is_a_complete_translation_and_canvas_resize_preserves_shape():
    p = settings('silhouette', scale=.22, center_x=.5, center_y=.4, neck_length=0., softness=0.)
    preset = head_preset(); source = np.zeros((240, 320, 3), np.float32)
    first = render_silhouette(source, p, 0, preset, 0)
    moved = render_silhouette(source, p, 0, dict(preset, object_x=24., object_y=12.), 0)
    assert np.array_equal(moved[20:-8, 32:-8], first[8:-20, 8:-32])
    resized = dict(preset, **resize_canvas(preset, {'width': 400, 'height': 320}))
    larger = render_silhouette(np.zeros((320, 400, 3), np.float32), p, 0, resized, 0)
    assert np.array_equal(larger[40:280, 40:360], first)


@pytest.mark.parametrize('module,renderer', [('edge_phosphor', render_edge_phosphor), ('scan_drag', render_scan_drag)])
def test_treatments_bypass_hold_freeze_and_seek_without_mutation(module, renderer):
    preset = head_preset(); source = np.zeros((80, 120, 3), np.float32)
    source[12:65, 42:84] = (1., .8, .7); original = source.copy()
    p = settings(module, rate=5.)
    if module == 'scan_drag': p.update(overload=1., window=1.)
    assert renderer(source, dict(p, mix=0.), .2, preset, 4) is source
    first = renderer(source, p, .01, preset, 4)
    assert np.array_equal(first, renderer(source, p, .19, preset, 4))
    assert not np.array_equal(first, renderer(source, p, .21, preset, 4))
    assert np.isfinite(renderer(source, p, 1_000_000., preset, 4)).all()
    assert np.array_equal(first, renderer(source, p, .01, preset, 4))
    frozen = dict(p, rate=0.)
    assert np.array_equal(renderer(source, frozen, .01, preset, 4), renderer(source, frozen, 99., preset, 4))
    assert np.array_equal(source, original)


def test_empty_signal_cannot_create_luminous_streaks_and_rightward_drag_uses_source_color():
    preset = head_preset(); black = np.zeros((120, 160, 3), np.float32)
    p = settings('scan_drag', overload=1., window=1., amount=1., density=1., jitter=0., tearing=0., chroma=0., grain=0., softness=0., gain=0., tint=0., dropout=0.)
    assert not render_scan_drag(black, p, 1., preset, 9).any()
    assert render_edge_phosphor(black, settings('edge_phosphor'), 1., preset, 9) is black
    source = black.copy(); source[:, 55:60, 1] = 1.
    result = render_scan_drag(source, p, 1., preset, 9)
    assert result[:, 80:120, 1].mean() > .6
    assert not result[..., (0, 2)].any()
    assert not result[:, :40].any()


def test_new_starter_has_four_sections_fixed_pose_and_editable_color_and_tear_states(tmp_path):
    project = profile_signal_composition(); sequence = compile_composition(project)
    assert len(project['sections']) == 4 and sequence['fps'] == 15
    assert round(sequence['duration'] * 15) == 61
    assert active_subjects(describe_effects(scope_states(project))) == ('silhouette',)
    poses = [{k: v for k, v in s['overrides'].items() if k.startswith('silhouette.')} for s in sequence['states'].values()]
    assert all(pose == poses[0] for pose in poses)
    path = tmp_path / 'profile.json'; save_composition(path, project)
    assert load_composition(path) == project
    path = tmp_path / 'detailed.json'; save_sequence(path, sequence)
    assert load_sequence(path) == sequence
    for time in (0., 1.1, 2.3, 3.5):
        assert render_sequence_frame(load_sequence(path), time, (240, 135)).tobytes() == render_sequence_frame(sequence, time, (240, 135)).tobytes()


def test_new_treatments_can_follow_another_object_and_restoring_keeps_original_pixels():
    project = profile_signal_composition(); replaced = select_subject(project, 'signal')
    info = describe_effects(scope_states(replaced))
    assert active_subjects(info) == ('signal',)
    assert info['edge_phosphor']['active'] and info['scan_drag']['active']
    original = render_sequence_frame(compile_composition(project), .4, (240, 135))
    assert original.tobytes() != render_sequence_frame(compile_composition(replaced), .4, (240, 135)).tobytes()
    assert original.tobytes() == render_sequence_frame(compile_composition(restore_subject(replaced)), .4, (240, 135)).tobytes()


def test_low_resolution_finish_retains_the_reference_texture_in_full_resolution():
    sequence = compile_composition(profile_signal_composition())
    preview = render_sequence_frame(sequence, 1.2, (480, 270))
    full = render_sequence_frame(sequence, 1.2)
    assert full.size == (960, 540)
    assert full.tobytes() == preview.resize(full.size, Image.Resampling.BILINEAR).tobytes()


def test_export_encodes_the_new_source_and_both_treatments(tmp_path):
    sequence = compile_composition(profile_signal_composition()); path = tmp_path / 'profile.mp4'
    export_synth_video(default_synth_preset(), path, count=2, sequence=sequence)
    probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'stream=width,height,nb_frames', '-of', 'json', str(path)], text=True))['streams'][0]
    assert (probe['width'], probe['height'], probe['nb_frames']) == (960, 540, '2')
    decoded = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(path), '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'])
    frame = np.frombuffer(decoded, dtype=np.uint8).reshape(2, 540, 960, 3)[0]
    assert np.abs(frame.astype(float) - np.asarray(render_sequence_frame(sequence, 0.), dtype=float)).mean() < 3


@pytest.mark.parametrize('size', [(480, 270), (270, 480)])
def test_neck_dissolve_removes_bright_tail_without_changing_the_face(size):
    seq = compile_composition(profile_signal_composition())
    if size[1] > size[0]:
        seq['canvas'] = resize_canvas(seq['canvas'], {'width': 1080, 'height': 1920})
    preset = _state_preset(seq, seq['cues'][0]['state'])
    source = render_silhouette(np.zeros((size[1], size[0], 3), np.float32), settings('silhouette'), 0., preset, 1)
    p = settings('edge_phosphor', grain=0.)
    before = render_edge_phosphor(source, p, 0., preset, 3)
    after = render_edge_phosphor(source, dict(p, neck_dissolve=1.), 0., preset, 3)
    neck = _neck_dissolve(preset, size, 1.)
    # Leave a small margin for the existing contour glow's blur footprint.
    first_neck_row = np.flatnonzero(neck.max(axis=1) > 0)[0]
    assert np.array_equal(before[:first_neck_row - 12], after[:first_neck_row - 12])
    tail = neck == 1
    # Green backlight has no blue; the stray violet contour must disappear.
    assert after[..., 2][tail].sum() < before[..., 2][tail].sum() * .02
    assert after[..., 1][tail].mean() > .015


def test_neck_dissolve_tracks_object_position_roll_and_scale_and_ignores_other_sources():
    seq = compile_composition(profile_signal_composition()); preset = _state_preset(seq, seq['cues'][0]['state'])
    preset.update(width=480, height=270)
    next(m['params'] for m in preset['modules'] if m['id'] == 'silhouette')['roll'] = 25.
    first = _neck_dissolve(preset, (480, 270), 1.)
    moved = _neck_dissolve(dict(preset, object_x=20., object_y=10.), (480, 270), 1.)
    assert np.allclose(first[:-10, :-20], moved[10:, 20:])
    larger = _neck_dissolve(preset, (960, 540), 1.)
    assert np.allclose(first, larger[::2, ::2])
    assert _neck_dissolve(preset, (480, 270), 0.) is None
    for m in preset['modules']:
        if m['id'] == 'silhouette': m['enabled'] = False
    source = np.zeros((270, 480, 3), np.float32); source[30:200, 120:250] = 1.
    p = settings('edge_phosphor')
    assert np.array_equal(render_edge_phosphor(source, p, 0., preset, 1), render_edge_phosphor(source, dict(p, neck_dissolve=1.), 0., preset, 1))
