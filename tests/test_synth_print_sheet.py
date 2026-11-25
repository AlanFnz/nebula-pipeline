"""Moving scans can expose new paper while retaining detail in overlapping areas."""
import hashlib

import numpy as np
import pytest

from nebula.effects.synth_print import MAX_PAPER_MOVEMENT, _scan_paper, render_print_surface
from nebula.render.synth import MODULE_BY_ID


def parameters(**changes):
    return dict({spec.key: spec.default for spec in MODULE_BY_ID['print_surface'].params}, **changes)


@pytest.mark.parametrize('surface,digest', [
    (0, 'f0f3809fa476820dad0b38491cdcd79744754b176bb5abb8e6f71677a168fdc7'),
    (1, '28e374394eebb801da1a122f0ab9772f4f238b409f252f954e5dbcfcb892f391'),
])
def test_saved_prints_keep_their_original_scan(surface, digest):
    image = np.random.default_rng(310).random((63, 91, 3), dtype=np.float32)
    settings = parameters(surface=surface, paper_motion=.28)
    for legacy in (settings, {k: v for k, v in settings.items() if k != 'paper_extent'}):
        result = render_print_surface(image, legacy, .25, 1., 111)
        assert hashlib.sha256(result.tobytes()).hexdigest() == digest


@pytest.mark.parametrize('size', [(106, 61), (61, 106), (79, 79)])
@pytest.mark.parametrize('dx,dy', [(1, 1), (-1, 1), (1, -1), (-1, -1)])
@pytest.mark.parametrize('layer,cell', [(0, 2.6), (1, 31.), (2, 3.9)])
def test_moving_window_exposes_distinct_stock_on_all_edges(size, dx, dy, layer, cell):
    w, h = size
    step = round(min(size) * MAX_PAPER_MOVEMENT)
    sx, sy = dx * step, dy * step
    original = _scan_paper(43, w, h, cell, layer, 0, 0, 1)
    moved = _scan_paper(43, w, h, cell, layer, sx, sy, 1)
    tiled = np.roll(original, (sy, sx), axis=(0, 1))
    common_x = slice(max(sx, 0), min(w + sx, w))
    common_y = slice(max(sy, 0), min(h + sy, h))
    new_x = slice(0, sx) if sx > 0 else slice(sx, None)
    new_y = slice(0, sy) if sy > 0 else slice(sy, None)
    np.testing.assert_allclose(moved[common_y, common_x], tiled[common_y, common_x], atol=1e-6)
    for region in ((common_y, new_x), (new_y, common_x), (new_y, new_x)):
        assert moved[region].std() > .01
        assert np.abs(moved[region] - tiled[region]).mean() > .02
    if layer == 1:
        # Linear interpolation of unit-range stock cannot jump by more than
        # one lattice cell's slope anywhere, including both former tile seams.
        for axis in (0, 1):
            assert np.abs(np.diff(moved, axis=axis)).max() <= 1 / cell + 1e-6


@pytest.mark.parametrize('surface', [0, 1])
def test_continuous_print_repeats_on_seek_and_holds_scan_cadence(surface):
    image = np.full((96, 66, 3), .3, np.float32)
    settings = parameters(surface=surface, paper_extent=1, paper_motion=.28, cadence=12)
    first = render_print_surface(image, settings, .251, 1., 52)
    later = render_print_surface(image, settings, .34, 1., 52)
    np.testing.assert_array_equal(first, render_print_surface(image, settings, .30, 1., 52))
    assert not np.array_equal(first, later)
    assert not np.array_equal(first, render_print_surface(image, dict(settings, paper_extent=0), .251, 1., 52))
