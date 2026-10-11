"""Whole-word ink transport and contour interpolation, independent of frame history.

Cached word fields use a fixed working grid. Horizontal ink quantiles carry the
strokes across unequal word widths before signed-distance interpolation changes
their topology. No character correspondence or opacity crossfade is required.
"""
from functools import lru_cache
import math

import numpy as np
from PIL import Image


def word_state(content, clock, hold, transition, loop):
    words = content.split()
    if not words: return '', '', 0.
    cycle = hold + transition
    index = max(0, int(clock / cycle))
    if not loop and index >= len(words) - 1: return words[-1], words[-1], 0.
    index %= len(words)
    progress = np.clip((clock % cycle - hold) / transition, 0., 1.)
    return words[index], words[(index + 1) % len(words)], float(progress)


def _distance(seeds):
    """Bounded octile distance transform; NumPy/Pillow only, cached per word."""
    h, w = seeds.shape
    d = np.where(seeds, 0., float(h + w)).astype(np.float32)
    x = np.arange(w, dtype=np.float32)
    for rows, previous in ((range(h), -1), (range(h - 1, -1, -1), 1)):
        for y in rows:
            other = y + previous
            if 0 <= other < h:
                d[y] = np.minimum(d[y], d[other] + 1.)
                d[y, 1:] = np.minimum(d[y, 1:], d[other, :-1] + 1.41421356)
                d[y, :-1] = np.minimum(d[y, :-1], d[other, 1:] + 1.41421356)
            d[y] = np.minimum.accumulate(d[y] - x) + x
            d[y] = (np.minimum.accumulate((d[y] + x)[::-1]))[::-1] - x
    return d


@lru_cache(maxsize=24)
def word_field(word, font, weight, tracking, height, width_limit, stretch_x, stretch_y, balance, grid):
    from synth_text import glyph_mask
    w, h = grid
    mask = glyph_mask(word, font, tracking, 1., 1, weight=weight)
    scale = min(height / mask.height, width_limit / max(1., mask.width * stretch_x))
    width = max(1, round(mask.width * scale * stretch_x))
    tall = max(1, round((mask.height * scale * (1 - balance) + height * balance) * stretch_y))
    # Legal extreme sizes can extend beyond the canvas; never allocate them.
    placed = mask.transform(grid, Image.Transform.AFFINE,
        (mask.width / width, 0, mask.width / 2 - w / 2 * mask.width / width,
         0, mask.height / tall, mask.height / 2 - h / 2 * mask.height / tall),
        Image.Resampling.BICUBIC)
    ink = np.asarray(placed, dtype=np.float32) / 255.
    inside = ink >= .5
    field = _distance(~inside) - _distance(inside)
    # Preserve antialiasing at the narrow serifs as well as thick stems.
    field = np.where(np.abs(field) <= 1., ink - .5, field - np.sign(field) * .5)
    quantiles = []
    for axis in (0, 1):
        mass = ink.sum(axis=axis) + .025
        cdf = (np.cumsum(mass) - mass * .5) / mass.sum()
        q = np.interp(np.linspace(0, 1, 1024), cdf, np.arange(len(mass))).astype(np.float32)
        q.setflags(write=False); quantiles.append(q)
    field.setflags(write=False)
    return field, *quantiles


def sample(field, x, y):
    h, w = field.shape
    x = np.clip(x, 0, w - 1.001); y = np.clip(y, 0, h - 1.001)
    ix = x.astype(np.int32); iy = y.astype(np.int32)
    fx, fy = x - ix, y - iy
    return ((field[iy, ix] * (1 - fx) + field[iy, ix + 1] * fx) * (1 - fy)
            + (field[iy + 1, ix] * (1 - fx) + field[iy + 1, ix + 1] * fx) * fy)


def morph_layout(p, clock, size, zoom=1.):
    cw, ch = size
    # Canonical geometry is independent of preview resolution and saved canvas.
    grid_scale = 576. / max(cw, ch)
    grid = max(32, round(cw * grid_scale)), max(32, round(ch * grid_scale))
    w, h = grid
    first, second, raw = word_state(p['content'], clock, p['morph_hold'], p['morph_seconds'], p['morph_loop'])
    if not first: return Image.new('L', grid), cw / w * zoom, ch / h * zoom
    eased = raw * raw * raw * (raw * (raw * 6 - 15) + 10)
    amount = raw + (eased - raw) * p['morph_ease']
    args = (p['font'], p.get('weight', 400), p['tracking'], h * p['size'], w * p['fit_width'], p['stretch_x'], p['stretch_y'], p['morph_balance'], grid)
    a, qa, ya = word_field(first, *args)
    b, qb, yb = word_field(second, *args)
    yy, xx = np.mgrid[:h, :w].astype(np.float32)
    mixed = qa * (1 - amount) + qb * amount
    ax = np.interp(np.arange(w), mixed, qa).astype(np.float32)[None, :]
    bx = np.interp(np.arange(w), mixed, qb).astype(np.float32)[None, :]
    mixed_y = ya * (1 - amount) + yb * amount
    ay = np.interp(np.arange(h), mixed_y, ya).astype(np.float32)[:, None]
    by = np.interp(np.arange(h), mixed_y, yb).astype(np.float32)[:, None]
    # Shared displacement keeps contours flowing through the transition; its
    # strength settles at endpoints so readable words retain their anatomy.
    envelope = math.sin(math.pi * amount)
    flow = p['morph_flow'] * h * (.0015 + .018 * envelope)
    dx = flow * (np.sin(yy / h * 18 + clock * 3.1) + .35 * np.sin(xx / w * 27 - clock * 2.3))
    dy = flow * (.65 * np.sin(xx / w * 14 + clock * 2.7) + .25 * np.sin(yy / h * 23 - clock * 1.9))
    field = sample(a, ax + dx, ay + dy) * (1 - amount) + sample(b, bx + dx, by + dy) * amount
    alpha = np.clip(field + .5, 0, 1)
    return Image.fromarray((alpha * 255).astype(np.uint8)), cw / w * zoom, ch / h * zoom
