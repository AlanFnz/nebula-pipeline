import copy
import hashlib

import numpy as np
from PIL import Image, ImageFilter

from synth import MODULE_BY_ID
from synth_composition import compile_composition, ink_bloom_composition
from synth_print import frame_noise_background, render_print_surface
from synth_sequence import render_sequence_frame


def params(**changes):
    return {**{p.key: p.default for p in MODULE_BY_ID['print_surface'].params}, **changes}


def figure_pixels(image):
    color = image.max(axis=2).astype(int) - image.min(axis=2) > 25
    # Isolated pale dust flecks belong to the background, not the white stamp.
    white = Image.fromarray(np.uint8(image.mean(axis=2) > 100) * 255)
    white_core = np.asarray(white.filter(ImageFilter.MinFilter(3))) > 0
    return color | white_core


def test_frame_noise_is_fresh_not_a_shift_or_repeated_tile():
    p = params(background_mode=1)
    a = frame_noise_background(360, 240, p, 0, 17)
    b = frame_noise_background(360, 240, p, 1, 17)
    # Find the strongest possible wrapped translation between frames. A shifted
    # tile would produce a large peak, even if ordinary pixel correlation is low.
    x = a - a.mean(); y = b - b.mean()
    correlation = np.fft.ifft2(np.fft.fft2(x) * np.conj(np.fft.fft2(y))).real
    assert np.abs(correlation).max() / (np.linalg.norm(x) * np.linalg.norm(y)) < .08
    assert not np.array_equal(a[:, :180], a[:, 180:])
    assert not np.array_equal(a[:120], a[120:])
    for tile in (a[:24, :24], a[:24, -24:], a[-24:, :24], a[-24:, -24:]):
        assert tile.mean() > .05 and tile.std() > .003
    frame_noise_background(360, 240, p, 1_000_000, 17)
    assert np.array_equal(a, frame_noise_background(360, 240, p, 0, 17))


def test_noise_uses_held_scan_clock_and_is_independent_of_the_sliding_paper():
    source = np.empty((120, 160, 3), dtype=np.float32)
    source[:] = (.055, .067, .055)
    p = params(background_mode=1)
    first = render_print_surface(source, p, .001, 1, 21)
    assert np.array_equal(first, render_print_surface(source, p, .05, 1, 21))
    assert not np.array_equal(first, render_print_surface(source, p, .07, 1, 21))
    other_paper = dict(p, paper_motion=.3, paper_grain=2., fibers=2., mottle=1., grain_size=8.)
    assert np.array_equal(first, render_print_surface(source, other_paper, .001, 1, 21))
    assert np.array_equal(render_print_surface(source, p, 0, 0, 21), render_print_surface(source, p, 20, 0, 21))
    assert np.array_equal(source, render_print_surface(source, dict(p, mix=0), .001, 1, 21))
    flat = frame_noise_background(160, 120, dict(p, noise_amount=0), 0, 21)
    assert np.all(flat == np.float32(p['noise_floor']))


def test_all_53_frames_preserve_the_approved_figures_and_original_paper_pixels():
    project = ink_bloom_composition()
    before = copy.deepcopy(project)
    overrides = before['source']['states']['print']['overrides']
    for key in list(overrides):
        if key == 'print_surface.background_mode' or key.startswith('print_surface.noise_'):
            del overrides[key]
    old = compile_composition(before); new = compile_composition(project)
    digest = hashlib.sha256()
    for frame in range(53):
        a = np.asarray(render_sequence_frame(old, frame / 15, (180, 180)))
        b = np.asarray(render_sequence_frame(new, frame / 15, (180, 180)))
        digest.update(a.tobytes())
        # Include neutral white ink as well as the colored figures and edges.
        ink = figure_pixels(a)
        assert np.array_equal(a[ink], b[ink]), frame
        assert not np.array_equal(a[:20, :20], b[:20, :20])
    # Recorded before the background change, including the existing ink wear.
    assert digest.hexdigest() == '3c475c56131e118a48fc588fc46a29785c1447a9d30f876574bf4c0384f402b9'


def test_background_controls_leave_figure_pixels_unchanged_on_a_story_canvas():
    project = ink_bloom_composition()
    project['canvas'].update(width=1080, height=1920)
    a = np.asarray(render_sequence_frame(compile_composition(project), 1.6, (180, 320)))
    project['effects']['print_surface'] = {'mode': 'recipe', 'params': {
        'print_surface.noise_amount': 1.8, 'print_surface.noise_size': 3.2,
        'print_surface.noise_clumps': .2, 'print_surface.noise_floor': .13,
    }}
    b = np.asarray(render_sequence_frame(compile_composition(project), 1.6, (180, 320)))
    ink = figure_pixels(a)
    assert np.array_equal(a[ink], b[ink])
    assert not np.array_equal(a[:30], b[:30])
