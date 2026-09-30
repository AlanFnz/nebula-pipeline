"""Phosphor contour/backlight over an image, bound to an optional spatial region.

This operator has no knowledge of heads, source module names or recipes.
"""
import math
import numpy as np
from PIL import Image, ImageFilter


def _blur(signal, radius):
    if radius <= 0: return signal
    image = Image.fromarray(np.clip(signal * 255, 0, 255).astype(np.uint8))
    return np.asarray(image.filter(ImageFilter.GaussianBlur(radius)), dtype=np.float32) / 255


def _hue(value):
    return np.clip(np.abs((value + np.array((0., 2 / 3, 1 / 3))) % 1 * 6 - 3) - 1, 0, 1)


def _rng(seed, time, speed, rate):
    tick = math.floor(time * speed * rate + 1e-9)
    return np.random.default_rng(np.random.SeedSequence((seed, tick & 0xffffffffffffffff)))


def _sample(signal, x, extend=False):
    """Horizontal bilinear sampling; optionally carry border color, never wrap."""
    h, w = signal.shape[:2]
    left = np.floor(x).astype(int); fraction = x - left
    y = np.arange(h)[:, None]
    weight = fraction if signal.ndim == 2 else fraction[..., None]
    result = signal[y, np.clip(left, 0, w - 1)] * (1 - weight) + signal[y, np.clip(left + 1, 0, w - 1)] * weight
    if extend: return result
    inside = (x >= 0) & (x <= w - 1)
    return result * (inside if signal.ndim == 2 else inside[..., None])


def render_phosphor(source, p, context, region=None, light_softness=.065):
    arr = source.image
    if p['mix'] == 0: return arr
    h, w = arr.shape[:2]; cw, ch = context.reference_size
    mask = source.signal_mask(p['threshold'])
    if not np.any(mask > .1): return arr
    rng = _rng(context.seed, context.held_time, context.speed, p['rate'])
    x = np.arange(w)[None, :]; y = np.arange(h)[:, None]
    side = -1 if p['side'] == 0 else 1
    edge = np.maximum(mask - _sample(mask, x + side * max(.7, p['rim_width'] * cw)), 0)
    rim = _blur(edge, .5 * cw / 480)
    rim *= 1 - p['lower_fade'] * np.clip((y / h - .74) / .24, 0, 1)
    fade = region.evaluate(context.size, source.frame) if region is not None else None
    if fade is not None:
        rim *= 1 - fade
    shifted = _sample(rim, x + side * p['separation'] * cw)
    glow = _blur(rim, p['glow'] * cw)
    present = (mask > .2).any(axis=1)
    boundary = np.argmax(mask > .2, axis=1) if side == -1 else w - 1 - np.argmax(mask[:, ::-1] > .2, axis=1)
    extend = p.get('canvas_coverage', 1) and context.reveal_canvas
    if extend and np.any(present):
        rows = np.flatnonzero(present)
        # Continue the lighting field past the source's finite height. Only the
        # atmosphere uses this guide; the projected mesh and contour stay put.
        guide = np.interp(np.arange(h), rows, boundary[rows])
        distance = (guide[:, None] - x) * -side / max(1., w, cw)
        gap = np.maximum(0, np.maximum(rows[0] - y, y - rows[-1]))
        feather = np.maximum(1., gap * .35) / max(1., w, cw)
        coverage = np.clip(1 + distance / feather, 0, 1)
        coverage = coverage * coverage * (3 - 2 * coverage)
        field = np.exp(-np.maximum(0, distance) / max(.001, p['spread'])) * coverage
    else:
        distance = (boundary[:, None] - x) * -side / max(1., cw)
        field = np.exp(-np.maximum(0, distance) / max(.001, p['spread'])) * (distance >= 0) * present[:, None]
    field *= 1 - mask
    if fade is not None:
        # Remove the hard cutout underneath the faded contour as well. Blend
        # the lighting field before grain so the fade joins fresh scan texture.
        field = field * (1 - fade) + _blur(field, cw * light_softness) * fade
    # The screen field is uneven on every held scan, not a translated tile.
    fine = rng.random((h, w))
    coarse = Image.fromarray(rng.integers(0, 256, (max(2, h // 18), max(2, w // 28)), dtype=np.uint8)).resize((w, h), Image.Resampling.BILINEAR)
    clumps = np.asarray(coarse, dtype=np.float32) / 255
    lines = rng.uniform(.4, 1.3, (h, 1))
    texture = np.maximum(0., 1 - p['grain'] + p['grain'] * (fine * 1.4 + clumps * .45) * lines)
    field *= texture * (.4 + .6 * np.exp(-((y / max(1, h) - .49) / .6) ** 2))
    primary = 1 - p['saturation'] + _hue(p['hue']) * p['saturation']; secondary = _hue(p['fringe_hue'])
    body = mask[..., None] * p['body']
    if fade is not None:
        body *= (1 - fade)[..., None]
    result = body + field[..., None] * primary * p['backlight']
    result += glow[..., None] * primary * p['edge'] * 2
    result += rim[..., None] * (primary * .75 + .25) * p['edge']
    result += shifted[..., None] * secondary * p['edge'] * p['fringe']
    # A rough secondary contour adds a faint recorded echo beside the face.
    echo = _sample(rim, x - side * p['echo_distance'] * cw)
    result += echo[..., None] * primary * p['echo'] * texture[..., None]
    return arr * (1 - p['mix']) + result * p['mix']
