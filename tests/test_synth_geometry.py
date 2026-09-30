import copy
import warnings

import numpy as np
import pytest
from PIL import ImageFilter

from synth import default_synth_preset, render_synth_frame
from synth_composition import compile_composition, load_composition, normalize_composition, reference_composition, save_composition, vary_composition
from synth_sequence import _interpolate_presets, render_sequence_frame


def clean_source(shape=0):
    preset = default_synth_preset()
    preset.update(depth=0., speed=0., animation={"targets": {}})
    preset["modules"] = [entry for entry in preset["modules"] if entry["id"] == "slab"]
    params = preset["modules"][0]["params"]
    params.update(shape=shape, width=.4, height=.6, diameter=.5, position_x=0., position_y=0., edge_softness=.005,
                  ghost_opacity=0., magenta=0., cyan=0., notch=0., jitter=0.)
    return preset, params


def mask(preset, size=(240, 192)):
    return np.asarray(render_synth_frame(preset, time_seconds=0., size=size)).mean(axis=2) > 80


def bounds(pixels):
    y, x = np.where(pixels)
    return x.max() - x.min() + 1, y.max() - y.min() + 1


@pytest.mark.parametrize("size", [(240, 192), (360, 180), (180, 240)])
def test_circle_diameter_is_physical_and_resolution_independent(size):
    preset, params = clean_source(2)
    width, height = bounds(mask(preset, size))
    assert abs(width - height) <= 2
    assert abs(height - .5 * size[1]) <= 3
    params["diameter"] = .3
    small = bounds(mask(preset, size))
    assert abs(small[1] - .3 * size[1]) <= 3
    assert small[0] < width


def test_ellipse_axes_and_rotation_use_image_pixels():
    preset, params = clean_source(1)
    narrow = bounds(mask(preset))
    params["width"] = .8
    wide = bounds(mask(preset))
    assert wide[0] >= narrow[0] * 1.9
    assert wide[1] == narrow[1]
    params["rotation"] = 90.
    rotated = bounds(mask(preset))
    assert abs(rotated[0] - wide[1]) <= 2
    assert abs(rotated[1] - wide[0]) <= 2


def test_circle_aperture_stays_round_when_rotating_the_ray_stack():
    preset = default_synth_preset()
    preset.update(depth=0., speed=0., animation={"targets": {}})
    preset["modules"] = [entry for entry in preset["modules"] if entry["id"] == "blinds"]
    params = preset["modules"][0]["params"]
    params.update(shape=2, diameter=.5, rows=18, thickness=.002, swelling=1., asymmetry=0.,
                  curvature=0., row_drift=0., irregularity=0., magenta=0.)
    for orientation in (0., .25, .5, 1.):
        params["orientation"] = orientation
        # Suppress thin outer rays to measure the bright aperture. The finite
        # ray spacing allows a small difference at its top/bottom boundaries.
        image = render_synth_frame(preset, size=(360, 240)).filter(ImageFilter.BoxBlur(2))
        width, height = bounds(np.asarray(image).mean(axis=2) > 80)
        assert abs(width - height) < 18
        assert 100 <= width <= 122 and 100 <= height <= 122


def test_more_polygon_sides_approach_a_circle_and_rotation_changes_the_contour():
    preset, params = clean_source(3)
    areas = []
    for sides in (3, 4, 6, 12, 32):
        params["sides"] = sides
        areas.append(mask(preset).sum())
    assert areas == sorted(set(areas))
    params["shape"] = 2
    circle_area = mask(preset).sum()
    assert .98 < areas[-1] / circle_area <= 1.
    params.update(shape=3, sides=3)
    triangle = mask(preset)
    params["rotation"] = 45.
    assert not np.array_equal(mask(preset), triangle)


@pytest.mark.parametrize("shape", ["rectangle", "ellipse", "circle", "polygon"])
def test_both_generators_render_finite_repeatable_geometry_with_treatment(shape):
    project = reference_composition(refined=True)
    project["geometry"].update(shape=shape, diameter=.5, sides=5, rotation=17.)
    sequence = compile_composition(project)
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        for t in (0., .64, 5.8, 11.6):
            a = render_sequence_frame(sequence, t, (180, 144)).tobytes()
            render_sequence_frame(sequence, 2.5, (180, 144))
            assert render_sequence_frame(sequence, t, (180, 144)).tobytes() == a
    for module in ("slab", "blinds"):
        assert sequence["states"]["section-1:blinds"]["overrides"][f"{module}.sides"] == 5


def test_geometry_inherits_can_be_overridden_locally_and_round_trips(tmp_path):
    project = reference_composition(refined=True)
    project["geometry"].update(shape="circle", diameter=.4)
    before = compile_composition(project)
    project["sections"][1]["geometry"].update(shape="polygon", diameter=.55, sides=3, rotation=25.)
    after = compile_composition(project)
    assert render_sequence_frame(before, 0., (120, 96)).tobytes() == render_sequence_frame(after, 0., (120, 96)).tobytes()
    assert render_sequence_frame(before, 6.2, (120, 96)).tobytes() != render_sequence_frame(after, 6.2, (120, 96)).tobytes()
    assert after["states"]["section-3:noisy"]["overrides"]["slab.diameter"] == .4
    path = tmp_path / "geometry.json"
    save_composition(path, project)
    assert load_composition(path) == project
    assert vary_composition(project)["geometry"] == project["geometry"]
    assert vary_composition(project, 1)["sections"][1]["geometry"] == project["sections"][1]["geometry"]


def test_legacy_documents_gain_neutral_geometry_and_height_scales_both_generators():
    project = reference_composition()
    legacy = copy.deepcopy(project)
    del legacy["geometry"]
    for section in legacy["sections"]:
        del section["geometry"]
    assert normalize_composition(legacy) == project
    base = compile_composition(project)
    project["geometry"]["height"] = .8
    changed = compile_composition(project)
    for t in (0., 5.8):
        assert render_sequence_frame(base, t, (120, 96)).tobytes() != render_sequence_frame(changed, t, (120, 96)).tobytes()


@pytest.mark.parametrize("field,value", [("shape", "star"), ("diameter", float("nan")), ("sides", 2), ("sides", 3.5), ("height", 0.), ("rotation", 181.)])
def test_invalid_geometry_is_rejected(field, value):
    project = reference_composition()
    project["geometry"][field] = value
    with pytest.raises(ValueError): normalize_composition(project)


def test_morph_switches_shape_types_and_rounds_polygon_sides():
    first, _ = clean_source(0)
    second, params = clean_source(3)
    params["sides"] = 9
    for amount in (.1, .49, .5, .8):
        result = _interpolate_presets(first, second, amount)
        values = result["modules"][0]["params"]
        assert values["shape"] == (0 if amount < .5 else 3)
        assert isinstance(values["sides"], int)
        render_synth_frame(result, size=(120, 96))
