import copy
from dataclasses import replace

import numpy as np
import pytest
from PIL import Image, ImageDraw

from synth import MODULE_BY_ID, curated_presets, default_synth_preset, normalize_synth, render_synth_frame
from synth_artwork import encode_artwork
from synth_canvas import resize_canvas
from synth_compat import starter_snapshot
from synth_composition import compile_composition, load_composition, normalize_composition, save_composition
from synth_profile import render_edge_phosphor, render_silhouette
from synth_profile_v1 import render_edge_phosphor as legacy_phosphor
from synth_regions import DirectionalRegion, LocalFrame
from synth_sequence import _state_preset, normalize_sequence, render_sequence_frame
from synth_source_adapters import phosphor_inputs, source_frame
from synth_starters import starter_composition


def params(module, **changes):
    return dict({p.key: p.default for p in MODULE_BY_ID[module].params}, **changes)


@pytest.mark.parametrize('strength', (0., .37, 1.))
@pytest.mark.parametrize('portrait', (False, True))
def test_generic_binding_matches_original_phosphor_before_quantization(strength, portrait):
    seq = compile_composition(starter_composition('profile-echoes'))
    if portrait:
        seq['canvas'] = resize_canvas(seq['canvas'], {'width': 1080, 'height': 1920})
    preset = _state_preset(seq, seq['cues'][0]['state'])
    preset.update(object_x=31., object_y=-17.)
    model = next(m['params'] for m in preset['modules'] if m['id'] == 'silhouette')
    model.update(roll=18., pitch=12., scale=.34)
    size = (90, 160) if portrait else (160, 90)
    arr = render_silhouette(np.zeros((size[1], size[0], 3), np.float32), model, .7, preset, 3)
    p = params('edge_phosphor', neck_dissolve=strength, body=.2)
    expected = legacy_phosphor(arr, p, .7, preset, 19)
    assert np.array_equal(expected, render_edge_phosphor(arr, p, .7, preset, 19))
    # An explicitly configured generic region reproduces the same recipe.
    p.update(fade_mode=1, fade_strength=strength, fade_start=.9, fade_width=.38)
    assert np.array_equal(expected, render_edge_phosphor(arr, p, .7, preset, 19))


def test_region_translation_rotation_scale_and_curve():
    frame = LocalFrame((40., 30.), 20.)
    region = DirectionalRegion(start=.1, width=.5, strength=.75)
    original = region.evaluate((100, 80), frame)
    moved = region.evaluate((100, 80), replace(frame, origin=(47., 35.)))
    assert np.array_equal(original[:-5, :-7], moved[5:, 7:])
    larger = region.evaluate((200, 160), LocalFrame((80., 60.), 40.))
    assert np.array_equal(original, larger[::2, ::2])
    assert original[30, 40] == 0 and original[-1, 40] == .75
    right = replace(region, angle=90.).evaluate((100, 80), frame)
    assert right[30, 40] == 0 and right[30, -1] == .75
    assert not np.array_equal(original, replace(region, smooth=False).evaluate((100, 80), frame))
    with pytest.raises(ValueError):
        replace(region, width=0.).evaluate((100, 80), frame)


@pytest.mark.parametrize('source', ('slab', 'ink_bloom'))
def test_same_directional_treatment_works_on_geometry_and_embedded_artwork(source):
    preset = default_synth_preset()
    preset.update(width=200, height=160, depth=0., speed=0.)
    for m in preset['modules']:
        m['enabled'] = m['id'] in (source, 'edge_phosphor')
        if m['id'] == 'slab':
            m['params'].update(position_x=0., position_y=0., height=.7, width=.8, notch=0., ghost_opacity=0., magenta=0., cyan=0.)
        if m['id'] == 'ink_bloom':
            mask = Image.new('L', (60, 80)); draw = ImageDraw.Draw(mask)
            draw.polygon(((2, 2), (55, 2), (55, 25), (30, 25), (30, 78), (2, 78)), fill=255)
            m['params'].update(shape=5, artwork=encode_artwork(mask), count=1, cycle=0., opening=0., size=.35,
                               tumble=0., tilt=0., turn=0., rotation=0., center_fold=0.)
    before = render_synth_frame(preset, size=(200, 160))
    edge = next(m['params'] for m in preset['modules'] if m['id'] == 'edge_phosphor')
    edge.update(fade_mode=1, fade_strength=1., fade_start=-.1, fade_width=.4)
    after = render_synth_frame(preset, size=(200, 160))
    assert before.tobytes() != after.tobytes()
    assert np.asarray(after)[110:, :, 2].sum() < np.asarray(before)[110:, :, 2].sum()
    first_frame = source_frame(preset, (200, 160), 0.)
    moved = source_frame(dict(preset, object_x=18., object_y=-6.), (200, 160), 0.)
    assert np.allclose(np.subtract(moved.origin, first_frame.origin), (18., -6.))


def test_canvas_region_does_not_follow_object_and_missing_anchor_is_explicit():
    preset = default_synth_preset(); arr = np.zeros((80, 100, 3))
    p = params('edge_phosphor', fade_mode=2, fade_strength=1.)
    first, context, region, _ = phosphor_inputs(arr, p, 1., preset, 3, 1.01)
    second, _, _, _ = phosphor_inputs(arr, p, 1., dict(preset, object_x=50.), 3)
    assert first.frame == second.frame
    assert context.continuous_time == 1.01 and context.held_time == 1.
    assert region is not None and first.coverage is None
    assert source_frame(preset, (100, 80), 0., 'silhouette') is None


def test_legacy_load_save_and_explicit_region_edit_choose_the_right_contract(tmp_path):
    old = starter_snapshot('profile-echoes'); original = copy.deepcopy(old)
    loaded = normalize_composition(old)
    assert loaded['render_version'] == 1 and old == original
    before = render_sequence_frame(compile_composition(loaded), .7, (160, 90)).tobytes()
    save_composition(tmp_path / 'old.json', loaded)
    assert load_composition(tmp_path / 'old.json') == loaded
    edited = copy.deepcopy(loaded)
    edited['effects']['edge_phosphor'] = {'mode': 'recipe', 'params': {
        'edge_phosphor.fade_mode': 1, 'edge_phosphor.fade_strength': 1.,
        'edge_phosphor.fade_start': .9, 'edge_phosphor.fade_width': .38}}
    assert normalize_composition(edited)['render_version'] == 2
    sequence = compile_composition(edited)
    assert sequence['render_version'] == 2
    assert render_sequence_frame(sequence, .7, (160, 90)).tobytes() == before
    save_composition(tmp_path / 'region.json', edited)
    assert render_sequence_frame(compile_composition(load_composition(tmp_path / 'region.json')), .7, (160, 90)).tobytes() == before
    assert loaded['render_version'] == 1
    with pytest.raises(ValueError, match='render version'):
        normalize_synth({'render_version': 100})
    with pytest.raises(ValueError, match='render version'):
        normalize_sequence(dict(sequence, render_version=True))


def test_legacy_defaults_and_starters_do_not_follow_live_parameter_defaults(monkeypatch):
    old = starter_snapshot('profile-echoes')
    before = render_sequence_frame(compile_composition(old), .7, (160, 90)).tobytes()
    module = MODULE_BY_ID['edge_phosphor']
    monkeypatch.setitem(MODULE_BY_ID, module.id, replace(module, params=tuple(replace(p, default=.8) if p.key == 'hue' else p for p in module.params)))
    assert render_sequence_frame(compile_composition(old), .7, (160, 90)).tobytes() == before
    assert render_sequence_frame(compile_composition(starter_composition('profile-echoes')), .7, (160, 90)).tobytes() == before
    old_preset = normalize_synth({'modules': [{'id': 'edge_phosphor'}]})
    assert old_preset['modules'][0]['params']['hue'] == .295
    assert curated_presets()['Reference blinds']['modules']
