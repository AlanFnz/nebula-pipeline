import numpy as np
import pytest

from nebula.effects.synth_photocopy import render_photocopy
from nebula.render.synth import MODULE_BY_ID


def plate(width=192, seconds=0., **changes):
    settings = {p.key: p.default for p in MODULE_BY_ID['photocopy'].params}
    settings.update(process=1, softness=0., edge_wear=0., light_depth=0., threshold=.5,
                    contrast=1., black=0., white=1., cadence=0., grain=0., pinholes=0.,
                    paper_grain=0., paper_tint=0., halftone=0.)
    settings.update(changes)
    image = np.zeros((width, width, 3), np.float32)
    image[:, width // 2:] = 1.
    return render_photocopy(image, settings, seconds, 283)


@pytest.mark.parametrize('setting,paper', [('paper_grain', True), ('paper_tint', True),
                                           ('grain', False), ('pinholes', False), ('edge_fade', False)])
def test_paper_and_ink_controls_are_independent(setting, paper):
    clean = plate()
    changed = plate(**{setting: .5})
    diff = np.abs(clean - changed)
    left, right = np.hsplit(diff, 2)
    active, other = (left, right) if paper else (right, left)
    assert active.max() > .01
    assert other.max() < 1e-6


def test_screen_crosses_the_ink_edge_and_resolves_into_tone_on_small_previews():
    settings = dict(halftone=.8, screen_angle=0., dot_size=8.)
    a = plate(360, **settings) - plate(360)
    # 180 pixels is an integer number of screen periods at this resolution.
    assert np.allclose(a[:, :180], a[:, 180:], atol=2e-5)
    assert a.std() > .02
    assert np.allclose(plate(90, **settings), plate(90))
    assert np.array_equal(plate(grain=1.), plate(seconds=2., grain=1.))
    assert not np.array_equal(plate(grain=1.), plate(seconds=2., grain=1., cadence=5.))
