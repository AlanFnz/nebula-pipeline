"""Guard the approved look and exercise the optional signal treatment."""
import copy
import hashlib

import numpy as np
import pytest

from synth import render_synth_frame
from synth_composition import compile_composition, reference_composition, save_composition, load_composition
from synth_sequence import _state_preset, reference_sequence, render_sequence_frame


def test_approved_frames_keep_the_pre_refinement_pixel_hash():
    # Captured before adding the new renderer parameters, not regenerated from
    # the current renderer during the test. Covers every treatment frame.
    sequence = reference_sequence()
    digest = hashlib.sha256()
    for frame in range(375):
        digest.update(render_sequence_frame(sequence, frame / 25, (96, 72)).tobytes())
    assert digest.hexdigest() == "4959175086abe01d22c0045f593113e6bc7c82f14481321b0ed7bc0ed1fc7f72"


@pytest.mark.parametrize("state,path,value", [
    ("slab", "slab.edge_ripple", .02),
    ("slab", "slab.cloud_detail", 1.),
    ("dimfilled", "slab.vertical_tint", 1.),
    ("blinds", "blinds.intensity", .4),
    ("blinds", "blinds.tail_spread", 1.),
    ("blinds", "blinds.edge_bias", .9),
    ("lower", "flare.asymmetry", .8),
    ("lower", "flare.bend", .8),
    ("slab", "raster.line_noise", .3),
])
def test_signal_parameters_are_visible_and_repeatable(state, path, value):
    source = reference_sequence()
    preset = _state_preset(source, state)
    baseline = render_synth_frame(preset, time_seconds=6.2, size=(240, 192)).tobytes()
    changed = copy.deepcopy(preset)
    module, key = path.split(".")
    next(item for item in changed["modules"] if item["id"] == module)["params"][key] = value
    frame = render_synth_frame(changed, time_seconds=6.2, size=(240, 192)).tobytes()
    assert frame != baseline
    render_synth_frame(changed, time_seconds=10., size=(240, 192))
    assert render_synth_frame(changed, time_seconds=6.2, size=(240, 192)).tobytes() == frame


def test_refined_recipe_roundtrip_and_local_macro_edits(tmp_path):
    project = reference_composition(refined=True)
    approved = reference_sequence()
    assert project["source"]["cues"] == approved["cues"]
    path = tmp_path / "refined.json"
    save_composition(path, project)
    assert load_composition(path) == project
    before = compile_composition(project)
    project["sections"][1]["macros"].update(texture=0., motion=0.)
    after = compile_composition(project)
    assert render_sequence_frame(before, 6.2).tobytes() != render_sequence_frame(after, 6.2).tobytes()
    assert render_sequence_frame(before, 11.6).tobytes() == render_sequence_frame(after, 11.6).tobytes()
    settings = after["states"]["section-2:slab"]["overrides"]
    assert settings["slab.edge_ripple"] == settings["slab.cloud_detail"] == settings["raster.line_noise"] == 0
    assert reference_sequence() == approved


def test_granular_cloud_still_respects_vertical_position():
    preset = _state_preset(reference_sequence(refined=True), "slab")
    params = next(item for item in preset["modules"] if item["id"] == "slab")["params"]
    params.update(cloud_detail=1., cloud_strength=0.)
    baseline = np.asarray(render_synth_frame(preset, time_seconds=2., size=(240, 192)), dtype=float)
    centers = []
    for offset in (-.4, .4):
        params.update(cloud_position=offset, cloud_strength=1.)
        changed = np.asarray(render_synth_frame(preset, time_seconds=2., size=(240, 192)), dtype=float)
        mass = np.maximum(changed - baseline, 0).sum(axis=(1, 2))
        centers.append(float(mass @ np.arange(192) / mass.sum()))
    assert centers[1] - centers[0] > 20
