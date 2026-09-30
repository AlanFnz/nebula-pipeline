import base64
import copy
import hashlib
from io import BytesIO

import numpy as np
import pytest
from PIL import Image, ImageDraw

from synth import MODULE_BY_ID, normalize_synth
from synth_artwork import ARTWORK_PREFIX, decode_artwork, encode_artwork, project_artwork, validate_artwork
from synth_composition import compile_composition, ink_bloom_composition, load_composition, save_composition
from synth_effects import normalize_effects
from synth_print import render_ink_bloom, stamp_outline
from synth_sequence import _interpolate_presets, _state_preset, render_sequence_frame


def cutout():
    image = Image.new('RGBA', (120, 160))
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 99, 139), fill=(100, 180, 30, 255))
    draw.rectangle((40, 45, 79, 99), fill=(0, 0, 0, 0))
    return image


def params(**changes):
    return {**{p.key: p.default for p in MODULE_BY_ID['ink_bloom'].params}, **changes}


def test_import_preserves_alpha_holes_and_proportions_and_can_invert_opaque_art():
    payload = encode_artwork(cutout())
    mask = decode_artwork(payload)
    assert mask.size == (80, 120)
    assert mask.getpixel((40, 60)) == 0
    assert mask.getpixel((2, 2)) == 255
    light = Image.new('RGB', (120, 160), 'black')
    light.paste(cutout(), mask=cutout().getchannel('A'))
    inverted = Image.fromarray(255 - np.asarray(light))
    assert encode_artwork(light, 'light') == encode_artwork(inverted, 'dark')
    with pytest.raises(ValueError, match='empty'): encode_artwork(Image.new('RGBA', (20, 20)))
    assert max(decode_artwork(encode_artwork(Image.new('RGB', (2400, 1200), 'white'))).size) == 2048


@pytest.mark.parametrize('value', [None, 4, {}, 'file:///tmp/art.png', ARTWORK_PREFIX + 'no png'])
def test_invalid_assets_are_rejected_in_presets_and_effects(value):
    with pytest.raises(ValueError): validate_artwork(value)
    with pytest.raises(ValueError): normalize_effects({'ink_bloom': {'params': {'ink_bloom.artwork': value}}})
    with pytest.raises(ValueError): normalize_synth({'modules': [{'id': 'ink_bloom', 'params': {'artwork': value}}]})


def test_embedded_asset_has_a_bounded_grayscale_format():
    for image in (Image.new('RGB', (10, 10), 'white'), Image.new('L', (2049, 1), 255)):
        buf = BytesIO(); image.save(buf, format='PNG')
        with pytest.raises(ValueError): decode_artwork(ARTWORK_PREFIX + base64.b64encode(buf.getvalue()).decode())


def test_cutout_projection_preserves_holes_and_handles_edge_on_planes():
    mask = decode_artwork(encode_artwork(cutout()))
    xy = np.array(((20, 10), (100, 10), (100, 130), (20, 130)), dtype=float)
    projected = np.asarray(project_artwork(mask, xy, (150, 150)))
    assert projected[70, 60] == 0
    assert projected[20, 30] == 255
    assert np.count_nonzero(projected[:, :15]) == 0
    edge_on = np.array(((20, 10), (20, 10), (20, 130), (20, 130)), dtype=float)
    assert not np.asarray(project_artwork(mask, edge_on, (150, 150))).any()


@pytest.mark.parametrize('shape', range(1, 6))
def test_shapes_share_motion_cadence_random_access_and_adaptive_framing(shape):
    p = params(shape=shape, artwork=encode_artwork(cutout()))
    source = np.zeros((180, 180, 3), np.float32)
    first = render_ink_bloom(source, p, .001, 1, 9)
    assert first.any()
    assert np.array_equal(first, render_ink_bloom(source, p, .05, 1, 9))
    opened = render_ink_bloom(source, p, 1.6, 1, 9)
    assert np.count_nonzero(opened) > np.count_nonzero(first) * 2
    render_ink_bloom(source, p, 1_000_000, 1, 9)
    assert np.array_equal(first, render_ink_bloom(source, p, .001, 1, 9))
    portrait = render_ink_bloom(np.zeros((320, 180, 3), np.float32), p, 1.6, 1, 9)
    assert np.allclose(opened, portrait[70:250], atol=1e-5)
    assert np.array_equal(first, render_ink_bloom(source, p, p['period'], 1, 9))


def test_shapes_have_editable_dimensions_and_side_count():
    for shape in (1, 2, 3, 4):
        p = params(shape=shape, sides=8)
        outline = stamp_outline(p, 8, 0)
        wide = stamp_outline(dict(p, shape_width=1.6, shape_height=.6), 8, 0)
        assert np.allclose(wide[:, 0], outline[:, 0] * 1.6)
        assert np.allclose(wide[:, 1], outline[:, 1] * .6)
        if shape == 4: assert len(outline) == 8
    empty = render_ink_bloom(np.zeros((80, 80, 3)), params(shape=5), 1, 1, 8)
    assert not empty.any()


def test_saved_original_burst_retains_all_53_approved_frames():
    project = ink_bloom_composition()
    # A document saved before replaceable artwork lacks these new controls.
    settings = project['source']['states']['print']['overrides']
    for name in ('shape', 'artwork', 'shape_width', 'shape_height', 'shape_rotation', 'sides'):
        settings.pop(f'ink_bloom.{name}')
    sequence = compile_composition(project)
    digest = hashlib.sha256()
    for frame in range(53): digest.update(render_sequence_frame(sequence, frame / 15, (180, 180)).tobytes())
    assert digest.hexdigest() == 'fbe93879547b20f48ebc89943fe8cf26b577458a15de488e6e86b927d21fb0dc'


def test_custom_artwork_round_trip_is_self_contained_and_transitions_are_discrete(tmp_path):
    path = tmp_path / 'cutout.png'; cutout().save(path)
    with Image.open(path) as image: artwork = encode_artwork(image)
    project = ink_bloom_composition(); before = copy.deepcopy(project['source'])
    project['effects']['ink_bloom'] = {'mode': 'recipe', 'params': {'ink_bloom.shape': 5, 'ink_bloom.artwork': artwork}}
    sequence = compile_composition(project)
    image = render_sequence_frame(sequence, 1.6, (180, 180)).tobytes()
    path.unlink()
    save_composition(tmp_path / 'portable.json', project)
    restored = load_composition(tmp_path / 'portable.json')
    assert restored == project and project['source'] == before
    assert render_sequence_frame(compile_composition(restored), 1.6, (180, 180)).tobytes() == image
    first = _state_preset(sequence, sequence['cues'][0]['state'])
    second = copy.deepcopy(first)
    other = next(m for m in second['modules'] if m['id'] == 'ink_bloom')['params']
    other.update(artwork='', shape=1)
    for amount, expected in ((.49, artwork), (.5, '')):
        middle = _interpolate_presets(first, second, amount)
        assert next(m for m in middle['modules'] if m['id'] == 'ink_bloom')['params']['artwork'] == expected
