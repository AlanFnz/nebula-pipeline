import copy
import hashlib

import numpy as np

from synth import _signal_background
from synth_canvas import resize_canvas
from synth_composition import compile_composition, profile_signal_composition
from synth_sequence import render_sequence_frame
from test_synth_profile import head_preset, settings


def test_signal_background_holds_freezes_seeks_and_preserves_bright_pixels():
    source = np.zeros((90, 160, 3), np.float32)
    source[20:70, 50:120] = (.4, .03, .8)
    original = source.copy(); p = settings('signal_background', rate=5.)
    preset = head_preset()
    a = _signal_background(source, p, .01, preset)
    assert np.array_equal(a, _signal_background(source, p, .19, preset))
    assert not np.array_equal(a, _signal_background(source, p, .21, preset))
    _signal_background(source, p, 1000000., preset)
    assert np.array_equal(a, _signal_background(source, p, .01, preset))
    frozen = dict(p, rate=0.)
    assert np.array_equal(_signal_background(source, frozen, 0., preset), _signal_background(source, frozen, 99., preset))
    assert np.array_equal(a[20:70, 50:120], source[20:70, 50:120])
    assert np.array_equal(source, original)
    assert _signal_background(source, dict(p, mix=0.), 0., preset) is source
    assert _signal_background(source, dict(p, level=0.), 0., preset) is source


def test_background_has_refined_green_black_tone_and_covers_canvas_independently_of_object():
    preset = head_preset(); p = settings('signal_background')
    for w, h in ((160, 90), (90, 160), (120, 120)):
        black = np.zeros((h, w, 3), np.float32)
        result = _signal_background(black, p, 0., preset)
        # Same lifted black range as Refined signal, with visible fine grain.
        assert .045 < result.mean() < .07
        assert result[..., 1].mean() > result[..., 0].mean()
        assert .01 < result.std() < .04
        for corner in (result[:10, :10], result[-10:, :10], result[:10, -10:], result[-10:, -10:]):
            assert corner.mean() > .04 and corner.std() > .01
        moved = dict(preset, object_x=50., object_y=-30.)
        assert np.array_equal(result, _signal_background(black, p, 0., moved))


def test_previous_profile_frames_are_exact_when_background_is_disabled():
    project = profile_signal_composition()
    project['effects']['signal_background'] = {'mode': 'off', 'params': {}}
    seq = compile_composition(project); digest = hashlib.sha256()
    for frame in range(61):
        digest.update(render_sequence_frame(seq, frame / 15, (120, 68)).tobytes())
    assert digest.hexdigest() == 'f0c0e7ff0a1f628c0a91e3e96af2af94cfbff7c145405d7f39b94f2efe465867'


def test_profile_shadows_share_the_texture_across_sections_and_canvas_formats():
    project = profile_signal_composition()
    for canvas in ({'width': 960, 'height': 540}, {'width': 540, 'height': 960}):
        framed = copy.deepcopy(project)
        framed['canvas'] = resize_canvas(project['canvas'], canvas)
        seq = compile_composition(framed)
        for time in (0., 1.1, 2.3, 3.5):
            image = np.asarray(render_sequence_frame(seq, time, (90, 160) if canvas['height'] > canvas['width'] else (160, 90)))
            assert image[-10:, -10:].mean() > 5
            assert image[-10:, -10:].std() > 1
