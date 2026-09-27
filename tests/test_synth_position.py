import copy

import numpy as np
import pytest

from synth import default_synth_preset, render_synth_frame
from synth_canvas import resize_canvas
from synth_composition import (compile_composition, composition_from_sequence, load_composition,
                               mixed_media_composition, normalize_composition, save_composition)
from synth_sequence import _interpolate_presets, load_sequence, render_sequence_frame, save_sequence
from synth_subject import select_subject


def isolated_source(kind):
    preset = default_synth_preset()
    preset.update(width=240, height=192, depth=0., speed=1., animation={'targets': {}})
    preset['modules'] = [entry for entry in preset['modules'] if entry['id'] == kind]
    entry = preset['modules'][0]; entry['enabled'] = True; p = entry['params']
    if kind == 'slab':
        p.update(width=.25, height=.45, position_x=-.15, ghost_opacity=.55, ghost_grain=0.,
                 ghost_offset=.35, ghost_width=.2, notch=0., jitter=0., edge_ripple=0.)
    elif kind == 'blinds':
        p.update(rows=9, orientation=.35, aperture=.4, aperture_height=.5, row_drift=0., curvature=0.)
    elif kind == 'particles':
        p.update(attractor=4, count=2500, scale=.6, occlusion=1., period=3., motion=2, release=1,
                 axis_mode=1, orbit_handoff=1, rotation_speed=18., orbit_speed=24., dispersion=.5)
    else:
        p.update(size=.08, spread=.13, shape=1)
    return preset


@pytest.mark.parametrize('kind', ['slab', 'blinds', 'particles', 'ink_bloom'])
def test_position_translates_complete_source_at_each_pose_without_changing_its_motion(kind):
    preset = isolated_source(kind)
    # Assembled, turning and expanded poses include satellites, ghosts and clouds.
    for time in (0., .8, 1.5, 2.7):
        original = np.asarray(render_synth_frame(preset, time_seconds=time))
        changed = np.asarray(render_synth_frame(dict(preset, object_x=24., object_y=-12.), time_seconds=time))
        # Compare the overlapping interior: translating generated geometry can
        # reveal formerly off-canvas content, which a shifted bitmap would lose.
        error = np.abs(changed[8:-20, 32:-8].astype(float) - original[20:-8, 8:-32].astype(float))
        assert error.mean() < .06
        assert not np.array_equal(original, changed)


def test_source_can_move_back_into_frame_without_losing_clipped_parts():
    preset = isolated_source('slab'); p = preset['modules'][0]['params']
    p.update(position_x=1., position_y=0., ghost_opacity=0., width=.3)
    moved = render_synth_frame(dict(preset, object_x=-60.))
    p['position_x'] -= 120 / (preset['width'] - 1)
    expected = render_synth_frame(preset)
    assert np.abs(np.asarray(moved).astype(float) - np.asarray(expected)).mean() < .01


def test_canvas_resize_and_proxy_keep_position_in_output_pixels():
    preset = isolated_source('slab'); preset.update(object_x=24., object_y=-12.)
    preset['modules'][0]['params']['ghost_opacity'] = 0.
    def center(image):
        y, x = np.where(np.asarray(image).max(axis=2) > 100)
        return np.array(((x.min() + x.max()) / 2, (y.min() + y.max()) / 2))
    original = center(render_synth_frame(preset))
    larger = dict(preset, **resize_canvas(preset, {'width': 384, 'height': 320}))
    assert center(render_synth_frame(larger)) - original == pytest.approx((72., 64.), abs=1.)
    # Halving a preview halves the pixel displacement, retaining visual placement.
    neutral = dict(larger, object_x=0., object_y=0.)
    delta = center(render_synth_frame(larger, size=(192, 160))) - center(render_synth_frame(neutral, size=(192, 160)))
    assert delta == pytest.approx((12., -6.), abs=1.)


def test_print_background_is_stationary_full_canvas_and_independent_of_object_position():
    project = mixed_media_composition()
    first = np.asarray(render_sequence_frame(compile_composition(project), 1.4, (240, 240)))
    project['geometry'].update(position_x=108., position_y=-54.)
    second = np.asarray(render_sequence_frame(compile_composition(project), 1.4, (240, 240)))
    assert not np.array_equal(first, second)
    for ys, xs in ((slice(0, 12), slice(0, 12)), (slice(-12, None), slice(-12, None))):
        assert np.array_equal(first[ys, xs], second[ys, xs])
        assert second[ys, xs].std() > 1
    empty = select_subject(project, 'none')
    moved = render_sequence_frame(compile_composition(empty), 1.4, (160, 160))
    empty['geometry'].update(position_x=0., position_y=0.)
    assert moved.tobytes() == render_sequence_frame(compile_composition(empty), 1.4, (160, 160)).tobytes()


def test_position_scope_persistence_source_switching_and_detailed_roundtrip(tmp_path):
    project = mixed_media_composition(); source = copy.deepcopy(project['source'])
    project['geometry'].update(position_x=100., position_y=-30.)
    project['sections'][1]['geometry'].update(position_x=20., position_y=10.)
    sequence = compile_composition(project)
    for name, state in sequence['states'].items():
        expected = (100., -30.) if name.startswith('section-1:') else (120., -20.)
        assert (state['overrides']['object_x'], state['overrides']['object_y']) == expected
    path = tmp_path / 'position.json'; save_composition(path, project)
    assert load_composition(path) == project
    assert select_subject(project, 'particles')['geometry'] == project['geometry']
    path = tmp_path / 'detail.json'; save_sequence(path, sequence)
    imported = compile_composition(composition_from_sequence(load_sequence(path)))
    for time in (1.4, 5.):
        assert render_sequence_frame(imported, time, (160, 160)).tobytes() == render_sequence_frame(sequence, time, (160, 160)).tobytes()
    assert project['source'] == source


def test_morph_interpolates_position_and_old_documents_default_to_neutral():
    first = isolated_source('slab'); second = dict(first, object_x=120., object_y=-80.)
    middle = _interpolate_presets(first, second, .25)
    assert middle['object_x'] == 30. and middle['object_y'] == -20.
    project = mixed_media_composition(); old = copy.deepcopy(project)
    for target in (old, *old['sections']):
        target['geometry'].pop('position_x'); target['geometry'].pop('position_y')
    assert normalize_composition(old) == project


@pytest.mark.parametrize('value', [float('nan'), float('inf'), 4097., -4097., True])
def test_invalid_object_position_is_rejected(value):
    project = mixed_media_composition(); project['geometry']['position_x'] = value
    with pytest.raises(ValueError): normalize_composition(project)


def test_export_uses_the_same_object_position_as_the_preview(tmp_path):
    import subprocess
    from synth_media import export_synth_video
    project = mixed_media_composition(); project['canvas'].update(width=240, height=192)
    project['geometry'].update(position_x=24., position_y=-12.)
    sequence = compile_composition(project); path = tmp_path / 'position.mp4'
    export_synth_video(default_synth_preset(), path, start=20, count=2, sequence=sequence)
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(path), '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'])
    frames = np.frombuffer(raw, dtype=np.uint8).reshape(2, 192, 240, 3)
    project['geometry'].update(position_x=0., position_y=0.)
    unshifted = compile_composition(project)
    for index, frame in enumerate(frames):
        expected = np.asarray(render_sequence_frame(sequence, (20 + index) / 15), dtype=float)
        # H.264 chroma subsampling softens the saturated ink edges. Compare
        # with the unmoved source as well, so the tolerance cannot hide a lost offset.
        error = np.abs(frame.astype(float) - expected).mean()
        wrong = np.asarray(render_sequence_frame(unshifted, (20 + index) / 15), dtype=float)
        assert error < 4
        assert error < np.abs(frame.astype(float) - wrong).mean() * .4
