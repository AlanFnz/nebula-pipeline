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


def test_pull_is_signed_broad_continuous_deterministic_and_resamples():
    image = np.full((192, 240, 3), (.055, .067, .055), dtype=np.float32)
    image[:, 95:145] = .8
    neutral = settings(**dict.fromkeys(('tracking', 'jitter', 'dropouts', 'chroma_delay', 'bleed', 'head_switch'), 0.), mix=1.)
    assert render_tape_damage(image, neutral, 4.2, 1., 7) is image
    right = render_tape_damage(image, dict(neutral, pull=.6), 4.2, 1., 7)
    left = render_tape_damage(image, dict(neutral, pull=-.6), 4.2, 1., 7)
    assert (np.abs(right-image).max(axis=(1,2)) > .01).mean() > .5
    assert right.max() <= .800001 and left.max() <= .800001
    assert np.argmax(right[96,:,0]) > np.argmax(image[96,:,0])
    assert np.argmax(left[96,:,0]) < np.argmax(image[96,:,0])
    assert np.array_equal(right, render_tape_damage(image, dict(neutral, pull=.6), 4.2, 1., 7))
    nearby = render_tape_damage(image, dict(neutral, pull=.6), 4.201, 1., 7)
    assert 0 < np.abs(nearby-right).max() < .02
    blank = np.full_like(image, (.055, .067, .055))
    assert np.allclose(render_tape_damage(blank, dict(neutral, pull=.6), 4.2, 1., 7), blank)


def test_pull_clock_is_independent_of_existing_fault_clock():
    image = np.random.default_rng(4).random((96,120,3)).astype('float32')
    worn = settings()
    assert np.array_equal(render_tape_damage(image,worn,.1,1.,7,pull_time=4.21), render_tape_damage(image,worn,.1,1.,7,pull_time=8.))
    # A fixed pull clock freezes only the new profile, keeping the old held faults.
    pulling = dict(worn,pull=.3,rate=5.)
    assert np.array_equal(render_tape_damage(image,pulling,.01,1.,7,pull_time=4.21), render_tape_damage(image,pulling,.19,1.,7,pull_time=4.21))
    assert not np.array_equal(render_tape_damage(image,pulling,.01,1.,7,pull_time=4.21), render_tape_damage(image,pulling,.21,1.,7,pull_time=4.21))


@pytest.mark.parametrize('width', [64, 121, 720])
def test_anchored_pull_coordinates_stay_monotonic_and_inside_canvas(width):
    from synth_tape import _anchored_pull_shifts
    shifts = _anchored_pull_shifts(width, np.linspace(-.42, .42, 31))
    source = np.arange(width)[None, :] - shifts
    assert np.all(source >= 0) and np.all(source <= width-1)
    assert np.all(np.diff(source, axis=1) > 0)
    assert np.all(source[:,0] == 0) and np.all(source[:,-1] == width-1)
    midpoint = width//2
    assert source[0,midpoint] > midpoint and source[-1,midpoint] < midpoint


@pytest.mark.parametrize('pull', [-1., -.18, .18, 1.])
def test_filled_pull_keeps_textured_canvas_edges_and_introduces_no_black(pull):
    image = (.35 + .4*np.random.default_rng(4).random((96,120,3))).astype('float32')
    neutral = settings(**dict.fromkeys(('tracking','jitter','dropouts','chroma_delay','bleed','head_switch'),0.),mix=1.)
    p = dict(neutral, pull=pull, pull_edges=1)
    result = render_tape_damage(image,p,4.07,1.,7)
    assert result.min() >= image.min()-1e-7 and result.max() <= image.max()+1e-7
    assert np.allclose(result[:,[0,-1]],image[:,[0,-1]],atol=1e-7)
    assert not np.allclose(result[:,30:90],image[:,30:90])
    assert render_tape_damage(image,dict(p,pull=0.),4.07,1.,7) is image
    # Blanking remains available for existing files and other fault treatments.
    blanked = render_tape_damage(image,dict(p,pull_edges=0),4.07,1.,7)
    assert blanked.min() < .1


def test_pull_edge_mode_does_not_change_unrelated_tape_faults():
    image = np.random.default_rng(8).random((96,120,3)).astype('float32')
    p = settings()
    assert np.array_equal(render_tape_damage(image,p,.31,1.,7),render_tape_damage(image,dict(p,pull_edges=1),.31,1.,7))
