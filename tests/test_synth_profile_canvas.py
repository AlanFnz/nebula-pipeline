import copy
import hashlib

import numpy as np
import pytest

from synth import MODULE_BY_ID, default_synth_preset
from synth_canvas import format_canvas, preview_size, resize_canvas
from synth_composition import compile_composition, profile_echoes_composition, profile_signal_composition
from synth_profile import render_edge_phosphor, render_scan_drag
from synth_sequence import render_sequence_frame


def params(module, **changes):
    return dict({p.key: p.default for p in MODULE_BY_ID[module].params}, **changes)


def reframed():
    preset = default_synth_preset()
    preset.update(width=160, height=90, speed=1.)
    preset.update(resize_canvas(preset, {'width': 180, 'height': 320}))
    return preset


@pytest.mark.parametrize('side', [0, 1])
def test_backlight_continues_above_and_below_the_source_on_either_side(side):
    source = np.zeros((320, 180, 3), np.float32)
    source[120:210, 75:125] = 1.
    original = source.copy(); p = params('edge_phosphor', side=side, grain=0.)
    result = render_edge_phosphor(source, p, 0., reframed(), 5)
    column = 10 if side == 0 else 170
    assert result[:30, column].max(axis=1).mean() > .15
    assert result[-30:, column].max(axis=1).mean() > .15
    legacy = render_edge_phosphor(source, dict(p, canvas_coverage=0), 0., reframed(), 5)
    assert not legacy[:30].any() and not legacy[-30:].any()
    assert np.array_equal(source, original)
    assert render_edge_phosphor(source, dict(p, mix=0.), 0., reframed(), 5) is source
    assert np.isfinite(result).all()


def test_scan_streaks_cross_the_old_recording_boundary_without_wrapping_or_black_edges():
    source = np.zeros((320, 180, 3), np.float32)
    source[:, :75, 1] = .3
    source[:, 75:82, 1] = 1.
    p = params('scan_drag', amount=1., density=1., jitter=0., tearing=.05,
               blocks=0, chroma=0., grain=0., softness=0., dropout=0., tint=0., gain=0.)
    result = render_scan_drag(source, p, 0., reframed(), 3)
    assert result[:, -8:, 1].mean() > .7
    assert result[:, :8, 1].mean() > .2
    assert not result[..., (0, 2)].any()
    legacy = render_scan_drag(source, dict(p, canvas_coverage=0), 0., reframed(), 3)
    assert not legacy[:, -8:].any() and not legacy[:, :8].any()
    black = np.zeros_like(source)
    assert not render_scan_drag(black, p, 0., reframed(), 3).any()


@pytest.mark.parametrize('module,renderer', [('edge_phosphor', render_edge_phosphor), ('scan_drag', render_scan_drag)])
def test_extended_treatments_keep_held_clocks_freeze_and_seek(module, renderer):
    source = np.zeros((320, 180, 3), np.float32); source[120:210, 75:125] = 1.
    p = params(module, rate=5.); preset = reframed()
    first = renderer(source, p, .01, preset, 7)
    assert np.array_equal(first, renderer(source, p, .19, preset, 7))
    assert not np.array_equal(first, renderer(source, p, .21, preset, 7))
    renderer(source, p, 1000., preset, 7)
    assert np.array_equal(first, renderer(source, p, .01, preset, 7))
    assert np.array_equal(renderer(source, dict(p, rate=0.), 0., preset, 7), renderer(source, dict(p, rate=0.), 1000., preset, 7))


@pytest.mark.parametrize('factory,expected', [
    (profile_signal_composition, '81fb4953db613d9ebc02b633f19499b376c007af1d05a1e83137852fcc493d31'),
    (profile_echoes_composition, '08d1c93a869cc0edd2f9bd8417aba055a7cd36ba7ad475423af27810776fab94'),
])
def test_native_profile_clips_retain_every_pre_spill_frame(factory, expected):
    project = factory(); seq = compile_composition(project); digest = hashlib.sha256()
    for frame in range(round(seq['duration'] * seq['fps'])):
        digest.update(render_sequence_frame(seq, frame / seq['fps'], (120, 68)).tobytes())
    assert digest.hexdigest() == expected


@pytest.mark.parametrize('identifier', ['stories', 'portrait', 'square', 'wide'])
def test_saved_profile_without_new_settings_gets_edge_to_edge_light_on_resize(identifier):
    project = profile_echoes_composition()
    # Simulate an existing saved profile. Missing parameters use the new
    # behavior; resizing never rewrites the user's embedded source or pose.
    for state in project['source']['states'].values():
        for path in ('edge_phosphor.canvas_coverage', 'scan_drag.canvas_coverage'):
            state['overrides'].pop(path, None)
    source = copy.deepcopy(project['source'])
    project['canvas'] = resize_canvas(project['canvas'], format_canvas(identifier))
    seq = compile_composition(project)
    for time in (0., 2.5, 4.8, 6.2):
        frame = np.asarray(render_sequence_frame(seq, time, preview_size(project['canvas'], 480)))
        # Chroma reaches the newly exposed top and bottom left, not just the
        # existing full-canvas neutral noise which hid this regression before.
        for tile in (frame[:20, :20], frame[-20:, :20]):
            assert np.ptp(tile.astype(float).mean(axis=(0, 1))) > 8
    assert project['source'] == source
