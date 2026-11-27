"""A second impression uses the same ink coverage as the rest of the print."""
import hashlib

import numpy as np
import pytest

from nebula.documents.synth_composition import compile_composition, load_composition, save_composition
from nebula.documents.synth_media import render_output_frame
from nebula.documents.synth_sequence import render_sequence_frame
from nebula.documents.synth_starting_points import new_piece
from nebula.effects.synth_dye_transfer import render_dye_transfer
from nebula.effects.synth_effects import effect_preset
from nebula.render.synth import MODULE_BY_ID


def print_sample(**changes):
    settings = {p.key: p.default for p in MODULE_BY_ID['dye_transfer'].params}
    settings.update(paper_saturation=0., paper_light=1., ink_light=0.,
                    mask_ink_hue=0., mask_ink_saturation=1., mask_ink_light=1.,
                    mask_paper_hue=2/3, mask_paper_saturation=1., mask_paper_light=1.,
                    mask_shape=5, mask_softness=0., wash=0., dye=0., warp=0.,
                    erosion=0., drag_mix=0., softness=0., dust=0., grain=0., weave=0.)
    settings.update(changes)
    source = np.zeros((96, 128, 3), np.float32)
    source[:, :42] = 1.
    source[:, 42:84] = .5
    return render_dye_transfer(source, settings, 0., 1., 31, (128, 96))


@pytest.mark.parametrize('target,letter,paper', [
    (1, (1,0,0), (1,1,1)), (2, (0,0,0), (0,0,1)), (3, (1,0,0), (0,0,1)),
])
def test_cut_respects_ink_paper_and_partial_source_coverage(target, letter, paper):
    base = print_sample(mask_shape=0)
    result = print_sample(mask_target=target)
    np.testing.assert_array_equal(result[20,20], letter)
    np.testing.assert_array_equal(result[20,100], paper)
    coverage = 127 / 255
    np.testing.assert_allclose(result[20,60], np.multiply(letter,coverage) + np.multiply(paper,1-coverage),
                               atol=1e-6)
    np.testing.assert_allclose(result[75], base[75], atol=1e-6)
    halfway = print_sample(mask_target=target, mask_opacity=.5)
    np.testing.assert_allclose(halfway, (base+result)*.5, atol=1e-6)
    np.testing.assert_array_equal(print_sample(mask_target=target, mask_opacity=0), base)


def test_rough_mask_moves_with_its_plate_and_keeps_its_artwork_proportions():
    settings = dict(mask_target=2, mask_shape=4, mask_size=.4, mask_aspect=.6,
                    mask_x=.25, mask_irregularity=8.)
    plate = print_sample(**settings)
    rotated = print_sample(**dict(settings, mask_angle=90.))
    np.testing.assert_allclose(plate[48,96], (0,0,1), atol=1e-6)
    assert plate[48,111,0] > .99 and rotated[48,111,0] < .01
    translated = print_sample(**dict(settings, mask_x=.25+8/128))
    np.testing.assert_allclose(plate[:,85:118], translated[:,93:126], atol=1e-6)


def test_legacy_silhouettes_match_the_original_eight_bit_prints():
    settings = {s.key: s.default for s in MODULE_BY_ID['dye_transfer'].params
                if not s.key.startswith(('mask_ink_', 'mask_paper_'))
                and s.key not in ('mask_target', 'mask_irregularity')}
    settings.update(mask_size=.72, mask_opacity=.68, mask_angle=34,
                    ink_density=.41, ink_veil=.29, edge_leak=.3)
    source = np.random.default_rng(83).random((51, 79, 3), dtype=np.float32)
    digest = hashlib.sha256()
    for shape in range(4):
        frame = render_dye_transfer(source, dict(settings, mask_shape=shape), .2, 1., 31, (79, 51))
        digest.update(np.uint8(frame*255).tobytes())
    # Captured from the same source and four mask shapes in 0.145.0.
    assert digest.hexdigest() == '5338c218dd4de3f6ec0723a3cc207d016cadf96697059f9cb749907a38758fbc'


def test_preset_roundtrip_and_direct_seek_use_the_same_animated_mask(tmp_path):
    size = (160, 220)
    doc = new_piece('text', dict(width=size[0], height=size[1]), text='INK')
    doc['effects']['dye_transfer'] = effect_preset('dye_transfer', 4)
    base = compile_composition(doc)
    doc['sections'][0]['automations'] = [
        dict(id='plate', path='dye_transfer.mask_x', amount=.2, start_fraction=.25,
             attack_fraction=.1, hold_fraction=.3, recovery_fraction=.1, enabled=True, easing='smooth')]
    path = tmp_path/'poster.nebula'
    save_composition(path, doc)
    restored = compile_composition(load_composition(path))
    for index in (75, 0, 149, 75):
        preview = render_sequence_frame(restored, index/restored['fps'], size=size)
        still = render_output_frame(None, restored, index, size, None)
        assert preview.tobytes() == still.tobytes()
        original = render_output_frame(None, base, index, size, None)
        assert (still.tobytes() != original.tobytes()) == (index == 75)


def test_corner_cuts_and_density_gradient_follow_the_plate():
    settings = dict(mask_target=2, mask_shape=6, mask_size=.8, mask_aspect=1.,
                    mask_inset_x=.5, mask_inset_y=.5, mask_paper_light=.55)
    sample = print_sample(**settings)
    assert sample[15, 96, 0] > .99 and sample[48, 96, 0] < .01
    uncut = print_sample(**dict(settings, mask_inset_x=0.))
    np.testing.assert_array_equal(uncut, print_sample(**dict(settings, mask_shape=4)))
    plain = print_sample(**dict(settings, mask_shape=0))
    ramp = print_sample(**dict(settings, mask_density_ramp=.65))
    assert ramp[32, 90, 2] > ramp[64, 90, 2]
    np.testing.assert_array_equal(ramp[15, 96], plain[15, 96])
    turned = print_sample(**dict(settings, mask_angle=180., mask_density_ramp=.65))
    np.testing.assert_allclose(turned[32, 90], ramp[64, 90], atol=1e-6)


def test_independent_impressions_expose_the_color_beneath_them():
    settings = dict(mask_shape=5, mask_target=2, mask_paper_light=.6)
    solid = print_sample(**settings)
    second = print_sample(**settings, mask_dry_ink=1.)
    source = print_sample(**settings, dry_ink=1.)
    # Ignore the optical spread along the cut and the source boundary.
    np.testing.assert_array_equal(second[65:, 90:], solid[65:, 90:])
    np.testing.assert_array_equal(second[8:36, 8:32], solid[8:36, 8:32])
    assert second[8:36, 90:, 0].max() > .05
    np.testing.assert_array_equal(source[:, 90:], solid[:, 90:])
    assert source[8:36, 8:32, 2].mean() > source[8:36, 8:32, 0].mean()
    veiled = print_sample(**settings, ink_veil_mode=1, ink_veil=1., ink_veil_x=-.3, ink_veil_y=-.25)
    assert veiled[24, 26, 2] > .45 and veiled[24, 26, 0] < .01
    np.testing.assert_array_equal(veiled[70:, :32], solid[70:, :32])
    np.testing.assert_array_equal(veiled[:, 90:], solid[:, 90:])
    single = print_sample(mask_shape=0, ink_veil_mode=1, ink_veil=1., ink_veil_x=-.3, ink_veil_y=-.25)
    assert single[24, 26].min() > .75
    hidden = print_sample(**settings, ink_veil_mode=1, ink_veil=1., mask_opacity=0.)
    np.testing.assert_array_equal(hidden, print_sample(**settings, mask_opacity=0.))


def test_dry_print_holds_on_seek_and_keeps_the_same_unprinted_sheet():
    settings = dict(mask_shape=6, mask_target=2, stock_relief=.6, fiber_size=1.4,
                    dry_ink=.4, mask_dry_ink=.8, cadence=0., dust=0., grain=0.,
                    wash=0., weave=0., warp=0., erosion=0., drag_mix=0., dye=0.)
    params = {p.key: p.default for p in MODULE_BY_ID['dye_transfer'].params}
    params.update(settings)
    image = np.zeros((112, 150, 3), np.float32)
    def sample(time):
        return render_dye_transfer(image, params, time, 1., 717, (150, 112))
    first = sample(0.)
    np.testing.assert_array_equal(first, sample(2.))
    params['cadence'] = 4.
    refreshed = sample(.27)
    np.testing.assert_allclose(refreshed[:, :8], first[:, :8], atol=1e-7)
    assert not np.array_equal(refreshed[42:74, 56:93], first[42:74, 56:93])
    np.testing.assert_array_equal(first, sample(.12))
    params.update(emulsion=.3, mask_density_ramp=.5)
    film = sample(.12)
    assert film.shape == first.shape and np.isfinite(film).all()
    assert not np.array_equal(film, first)


def test_exposed_paper_and_second_plate_have_separate_grain_sizes():
    base = print_sample(mask_target=2)
    paper = print_sample(mask_target=2, paper_grain=.9, paper_grain_size=6.)
    np.testing.assert_array_equal(paper[:, :39], base[:, :39])  # solid source ink
    np.testing.assert_allclose(paper[5:32, 90:], base[5:32, 90:], atol=1e-7)  # solid plate
    assert not np.array_equal(paper[62:, 90:], base[62:, 90:])
    settings = dict(mask_target=2, mask_dry_ink=.8, stock_relief=.4, dry_ink=.5, fiber_size=1.5)
    inherited = print_sample(**settings)
    np.testing.assert_array_equal(inherited, print_sample(**settings, mask_grain_size=1.5))
    coarse = print_sample(**settings, mask_grain_size=6.)
    assert not np.array_equal(inherited[5:32, 90:], coarse[5:32, 90:])
    np.testing.assert_array_equal(inherited[62:], coarse[62:])
