import copy
import json
import subprocess

import numpy as np
import pytest

from synth import default_synth_preset, normalize_synth, render_synth_frame
from synth_canvas import CANVAS_FORMATS, format_canvas, normalize_canvas, preview_size
from synth_composition import compile_composition, composition_from_sequence, load_composition, particle_orbit_composition, save_composition
from synth_media import export_synth_video
from synth_sequence import _state_preset, load_sequence, render_sequence_frame, save_sequence
from synth_starters import STARTERS, starter_composition


@pytest.mark.parametrize("raw", [{"width": 0}, {"height": float("nan")}, {"width": 100.5}, {"width": True}, {"framing": "stretch"}, []])
def test_invalid_canvas_is_rejected(raw):
    with pytest.raises(ValueError):
        normalize_canvas(raw)


def test_canvas_is_separate_from_authored_scene_and_round_trips(tmp_path):
    project = particle_orbit_composition()
    original = copy.deepcopy(project)
    before = render_sequence_frame(compile_composition(project), 6.4, (180, 144)).tobytes()
    project["canvas"] = format_canvas("stories")
    seq = compile_composition(project)
    assert project["source"] == original["source"]
    assert project["sections"] == original["sections"]
    path = tmp_path / "story.json"
    save_composition(path, project)
    assert load_composition(path) == project
    save_sequence(path, seq)
    assert load_sequence(path)["canvas"] == project["canvas"]
    assert composition_from_sequence(load_sequence(path))["canvas"] == project["canvas"]
    project["canvas"] = format_canvas("original")
    assert render_sequence_frame(compile_composition(project), 6.4, (180, 144)).tobytes() == before


@pytest.mark.parametrize("identifier,label,width,height", CANVAS_FORMATS)
def test_formats_render_complete_canvases_and_keep_texture_at_all_edges(identifier, label, width, height):
    project = particle_orbit_composition(); project["canvas"] = format_canvas(identifier)
    seq = compile_composition(project)
    size = preview_size(project["canvas"], 320)
    image = np.asarray(render_sequence_frame(seq, 0., size))
    assert image.shape == (size[1], size[0], 3)
    # Newly generated texture reaches every edge; no image padding/letterbox.
    for tile in (image[:16, :16], image[:16, -16:], image[-16:, :16], image[-16:, -16:]):
        assert tile.std() > .5
        assert tile.mean() > 2.
    assert (seq["canvas"]["width"], seq["canvas"]["height"]) == (width, height)
    assert width % 2 == height % 2 == 0


def test_story_framing_preserves_head_shape_and_keeps_its_center_clear_of_edges():
    seq = compile_composition(particle_orbit_composition())
    preset = _state_preset(seq, seq["cues"][0]["state"])
    preset["modules"] = [m for m in preset["modules"] if m["id"] == "particles"]
    preset["framing"] = "adaptive"
    params = preset["modules"][0]["params"]
    params.update(breathing=0., turbulence=0., jitter=0., shimmer=0., rotation_speed=0.)
    # Compare an isolated head at matching times in native and story formats.
    sizes = []
    for size in ((540, 432), (243, 432)):
        image = np.asarray(render_synth_frame(preset, time_seconds=0., size=size))
        y, x = np.where(image.max(axis=2) > 80)
        sizes.append((np.ptp(x), np.ptp(y)))
        assert abs((x.min() + x.max()) / 2 - size[0] / 2) < size[0] * .1
        assert x.min() > size[0] * .1 and x.max() < size[0] * .9
        assert y.min() > size[1] * .1 and y.max() < size[1] * .9
    assert sizes[0][0] / sizes[0][1] == pytest.approx(sizes[1][0] / sizes[1][1], rel=.05)


def test_export_uses_saved_story_canvas_without_an_external_size_argument(tmp_path):
    project = particle_orbit_composition(); project["canvas"] = format_canvas("stories")
    project["sections"] = [project["sections"][0]]; project["sections"][0]["duration"] = .12
    seq = compile_composition(project)
    path = tmp_path / "story.mp4"
    export_synth_video(default_synth_preset(), path, sequence=seq)
    probe = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,nb_frames", "-of", "json", str(path)], text=True))["streams"][0]
    assert (probe["width"], probe["height"], probe["nb_frames"]) == (1080, 1920, "3")


def test_starters_are_independent_documents_and_preserve_all_studies():
    assert {entry[0] for entry in STARTERS} == {"refined", "approved", "particle-head", "particle-orbit", "original-particles", "ink-bloom", "mixed-media", "profile-signal", "profile-echoes", "profile-clear"}
    for identifier, _label, _factory in STARTERS:
        first = starter_composition(identifier); second = starter_composition(identifier)
        first["source"]["states"].clear()
        first["canvas"] = format_canvas("stories")
        assert second == starter_composition(identifier)
        assert second["source"]["states"]


def test_preset_canvas_and_custom_sequence_dimensions_are_used_without_a_proxy():
    preset = normalize_synth(dict(default_synth_preset(), width=90, height=160, framing="adaptive"))
    assert render_synth_frame(preset).size == (90, 160)
    project = particle_orbit_composition(); project["canvas"] = normalize_canvas(preset)
    assert render_sequence_frame(compile_composition(project), 0).size == (90, 160)
