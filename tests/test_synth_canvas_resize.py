import copy

import numpy as np
import pytest

from synth import default_synth_preset, render_synth_frame
from synth_canvas import normalize_canvas, resize_canvas
from synth_composition import compile_composition, load_composition, mixed_media_composition, save_composition
from synth_sequence import render_sequence_frame


def source(kind):
    preset = default_synth_preset(); preset.update(width=240, height=192, depth=0., speed=0., animation={'targets': {}})
    module = 'slab' if kind in ('rectangle', 'ellipse') else kind
    preset['modules'] = [m for m in preset['modules'] if m['id'] == module]
    entry = preset['modules'][0]; entry['enabled'] = True; p = entry['params']
    if module == 'slab':
        p.update(shape=0 if kind == 'rectangle' else 1, width=.4, height=.6, position_x=0., position_y=0.,
                 edge_softness=.005, ghost_opacity=0., cloud_strength=0., magenta=0., cyan=0., notch=0., jitter=0.)
    elif module == 'blinds':
        p.update(rows=12, aperture=.4, aperture_height=.6, thickness=.002, swelling=.7, asymmetry=0.,
                 curvature=0., row_drift=0., irregularity=0., magenta=0.)
    elif module == 'particles':
        p.update(count=2000, breathing=0., turbulence=0., jitter=0., shimmer=0., rotation_speed=0.)
    else:
        p.update(cycle=0., opening=.6, shape=1, size=.13, spread=.2)
    return preset


def subject_bounds(image, threshold):
    y, x = np.where(np.asarray(image).max(axis=2) > threshold)
    return np.array((x.min(), y.min(), x.max(), y.max()))


@pytest.mark.parametrize('kind', ['rectangle', 'ellipse', 'blinds', 'particles', 'ink_bloom'])
def test_canvas_resize_retains_element_size_proportions_and_center(kind):
    preset = source(kind); original = copy.deepcopy(preset)
    threshold = 205 if kind == 'blinds' else 80
    first = subject_bounds(render_synth_frame(preset, time_seconds=0.), threshold)
    for width, height in ((400, 192), (240, 400), (200, 300)):
        canvas = resize_canvas(normalize_canvas(preset), {'width': width, 'height': height})
        changed = dict(preset, **canvas)
        bounds = subject_bounds(render_synth_frame(changed, time_seconds=0.), threshold)
        offset = np.array(((width - 240) / 2, (height - 192) / 2) * 2)
        assert bounds - offset == pytest.approx(first, abs=1)
    assert preset == original


def test_canvas_crops_center_without_resampling_the_original_rectangle():
    preset = source('rectangle')
    first = render_synth_frame(preset, time_seconds=0.)
    changed = dict(preset, **resize_canvas(preset, {'width': 120, 'height': 100}))
    cropped = render_synth_frame(changed, time_seconds=0.)
    assert cropped.tobytes() == first.crop((60, 46, 180, 146)).tobytes()


def test_repeated_canvas_edits_keep_one_reference_and_fit_scales_uniformly():
    preset = source('rectangle'); original = normalize_canvas(preset)
    first = resize_canvas(original, {'width': 400, 'height': 600})
    second = resize_canvas(first, {'width': 120, 'height': 192}, fit=True)
    assert first['reference'] == second['reference'] == original
    bounds = subject_bounds(render_synth_frame(dict(preset, **second), time_seconds=0.), 80)
    base = subject_bounds(render_synth_frame(preset, time_seconds=0.), 80)
    assert bounds[2:] - bounds[:2] + 1 == pytest.approx((base[2:] - base[:2] + 1) * .5, abs=1)
    restored = resize_canvas(second, original)
    assert render_synth_frame(dict(preset, **restored), time_seconds=0.).tobytes() == render_synth_frame(preset, time_seconds=0.).tobytes()


def test_resized_canvas_keeps_background_at_edges_and_survives_save(tmp_path):
    project = mixed_media_composition(); source_before = copy.deepcopy(project['source'])
    project['canvas'] = resize_canvas(project['canvas'], {'width': 1080, 'height': 1920})
    path = tmp_path / 'canvas.json'; save_composition(path, project)
    assert load_composition(path) == project and project['source'] == source_before
    image = np.asarray(render_sequence_frame(compile_composition(project), 1.4, (202, 360)))
    for corner in (image[:16, :16], image[-16:, :16], image[:16, -16:], image[-16:, -16:]):
        assert corner.std() > .5
        assert corner.mean() > 2


@pytest.mark.parametrize('reference', [[], {'width': 0}, {'framing': 'fit'}, {'reference': {}}])
def test_invalid_artwork_reference_is_rejected(reference):
    with pytest.raises(ValueError): normalize_canvas({'reference': reference, 'framing': 'preserve'})
