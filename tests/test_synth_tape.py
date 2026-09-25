"""Tape faults consume the existing signal rather than generating new bars."""
import numpy as np
import pytest

from synth import MODULE_BY_ID
from synth_tape import render_tape_damage


def settings(**overrides):
    return {**{p.key: p.default for p in MODULE_BY_ID["tape"].params}, **overrides}


def test_tape_never_generates_shapes_on_the_blank_signal_and_bypasses_exactly():
    blank = np.full((96, 120, 3), (.055, .067, .055), dtype=np.float32)
    p = settings(tracking=.3, jitter=.02, dropouts=1., chroma_delay=.08, bleed=.12, head_switch=1., mix=1.)
    assert np.allclose(render_tape_damage(blank, p, 2.3, 1., 7), blank, atol=1e-8)
    image = np.random.default_rng(4).random((96, 120, 3)).astype("float32")
    assert render_tape_damage(image, settings(mix=0.), 0., 1., 7) is image
    neutral = settings(**dict.fromkeys(("tracking", "jitter", "dropouts", "chroma_delay", "bleed", "head_switch"), 0.))
    assert render_tape_damage(image, neutral, 0., 1., 7) is image


@pytest.mark.parametrize("key", ["tracking", "jitter", "dropouts", "chroma_delay", "bleed", "head_switch"])
def test_individual_faults_modify_the_source_without_nonfinite_pixels(key):
    image = np.random.default_rng(4).random((96, 120, 3)).astype("float32")
    p = settings(**dict.fromkeys(("tracking", "jitter", "dropouts", "chroma_delay", "bleed", "head_switch"), 0.))
    p[key] = settings()[key]
    result = render_tape_damage(image, p, 2.3, 1., 7)
    assert np.isfinite(result).all()
    assert not np.allclose(result, image)


def test_tape_is_random_access_and_holds_at_its_fault_rate():
    image = np.random.default_rng(4).random((96, 120, 3)).astype("float32")
    p = settings(rate=5.)
    expected = render_tape_damage(image, p, .01, 1., 7)
    assert np.array_equal(expected, render_tape_damage(image, p, .19, 1., 7))
    assert not np.array_equal(expected, render_tape_damage(image, p, .21, 1., 7))
    render_tape_damage(image, p, 10000., 1., 7)
    assert np.array_equal(expected, render_tape_damage(image, p, .01, 1., 7))
    assert np.array_equal(expected, render_tape_damage(image, p, 50., 0., 7))
    assert np.array_equal(expected, render_tape_damage(image, dict(p, rate=0.), 50., 1., 7))


def test_tracking_resamples_rows_instead_of_adding_exposure():
    # A monochrome vertical edge can only move sideways; brightness stays bounded.
    image = np.full((192, 240, 3), (.055, .067, .055), dtype=np.float32)
    image[:, 95:145] = .8
    p = settings(tracking=.15, jitter=0., dropouts=0., chroma_delay=0., bleed=0., head_switch=0., mix=1.)
    result = render_tape_damage(image, p, 1., 1., 7)
    changed_rows = (np.abs(result - image).max(axis=(1, 2)) > .01)
    assert .01 < changed_rows.mean() < .5
    assert result.max() <= .800001
    assert np.all(result >= np.array((.055, .067, .055)) - 1e-7)
