import copy
import random
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

import analog_wobble as fx
from engine import render_frame, frame_values
from grade import process as grade_process
from parameters import DEFAULTS, normalize, load, save


def source():
    return Image.fromarray(np.random.default_rng(3).integers(0, 256, (80, 96, 3), dtype=np.uint8))


def test_scrub_determinism_and_global_rng_isolation():
    p = {**DEFAULTS, "bloom": .5, "curvature": .2, "drift": .8}
    random.seed(991)
    np.random.seed(337)
    state, np_state = random.getstate(), np.random.get_state()
    expected = render_frame(source(), p, 51).tobytes()
    for frame in [99, 4, 0, 20, 51]:
        image = render_frame(source(), p, frame)
    assert image.tobytes() == expected
    assert random.getstate() == state
    assert np.array_equal(np.random.get_state()[1], np_state[1])


def test_effect_stream_isolation(monkeypatch):
    dust_samples, grain_samples, positions = [], [], []
    original_dust, original_grain, original_wobble = fx.add_dust, fx.add_luminous_grain, fx.wobble
    def dust(img, strength, opacity, rng):
        dust_samples.append(copy.deepcopy(rng.bit_generator.state))
        return original_dust(img, strength, opacity, rng)
    def grain(img, sigma, rng):
        grain_samples.append(copy.deepcopy(rng.bit_generator.state))
        return original_grain(img, sigma, rng)
    def wobble(img, dx, dy, angle):
        positions.append((dx, dy, angle))
        return original_wobble(img, dx, dy, angle)
    monkeypatch.setattr(fx, "add_dust", dust)
    monkeypatch.setattr(fx, "add_luminous_grain", grain)
    monkeypatch.setattr(fx, "wobble", wobble)
    render_frame(source(), DEFAULTS, 31)
    render_frame(source(), {**DEFAULTS, "blur": (0, 0), "texture": 0, "aberration": 0}, 31)
    render_frame(source(), {**DEFAULTS, "_stages": {"print": False}}, 31)
    assert dust_samples[0] == dust_samples[1] == dust_samples[2]
    assert grain_samples[0] == grain_samples[1] == grain_samples[2]
    assert positions[0] == positions[1] == positions[2]
    v = frame_values(DEFAULTS, 31)
    changed = frame_values({**DEFAULTS, "blur": (12, 20), "drift": .7}, 31)
    assert (v["dx"], v["dy"], v["angle"], v["grain"]) == (changed["dx"], changed["dy"], changed["angle"], changed["grain"])


def test_legacy_full_sequence_equals_preview(tmp_path):
    raw, wob, graded = [tmp_path / n for n in ("raw", "wob", "graded")]
    raw.mkdir()
    p = normalize({**DEFAULTS, "drift": .5, "bloom": .4, "scanlines": .2})
    for index in range(4):
        source().save(raw / f"frame_{index+1:05}.png")
    fx.process(raw, wob, p["px"], p["deg"], p["grain"], p["blur"],
               **{key: p[key] for key in ("aberration", "vignette", "bands", "texture", "warm", "dust", "dust_opacity", "scanlines", "bloom", "curvature", "brightness", "seed", "drift")},
               on_progress=lambda *_: None)
    grade_process(wob, graded, **{key: p[key] for key in ("contrast", "shadows", "highlights", "toning")}, on_progress=lambda *_: None)
    for index in range(4):
        assert Image.open(graded / f"frame_{index+1:05}.png").tobytes() == render_frame(source(), p, index).tobytes()


def test_stage_bypass_and_preset_roundtrip(tmp_path):
    p = normalize({**DEFAULTS, "grade": 0, "_stages": {"print": False, "scan": False, "wobble": False}})
    assert render_frame(source(), p, 14).tobytes() == source().tobytes()
    target = tmp_path / "tune_params.json"
    save(target, p)
    assert load(target) == p
    assert render_frame(source(), DEFAULTS, stage="source").tobytes() == source().tobytes()
    assert normalize({"seed": None})["seed"] == 42
    with pytest.raises(ValueError):
        normalize({"blur": [float("nan"), 1]})
