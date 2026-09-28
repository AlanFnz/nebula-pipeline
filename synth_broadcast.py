"""Reusable broadcast field, signal-loss intervals and curved screen treatment."""
import math

import numpy as np
from PIL import Image

from synth_text import color


def render_broadcast(arr, p, time, speed, seed):
    if not p['mix']: return arr
    h, w = arr.shape[:2]; clock = time * speed
    tick = math.floor(clock * p['rate'] + 1e-8)
    rng = np.random.default_rng(np.random.SeedSequence((seed, tick & 0xffffffffffffffff)))
    y, x = np.mgrid[:h, :w].astype(np.float32)
    x = (x + .5) / w * 2 - 1; y = (y + .5) / h * 2 - 1
    out = arr.copy()
    if p['field']:
        # Independent low-frequency fields crossfade rather than slide a tile.
        phase = clock * p['drift']; left = math.floor(phase); f = phase - left; f = f * f * (3 - 2 * f)
        fields = []
        for index in (left, left + 1):
            local = np.random.default_rng(np.random.SeedSequence((seed, index & 0xffffffffffffffff, 92)))
            grid = local.random((6, 8)).astype(np.float32)
            fields.append(np.asarray(Image.fromarray(grid).resize((w, h), Image.Resampling.BICUBIC)))
        field = fields[0] * (1 - f) + fields[1] * f
        a = color(p['hue'], .95, 1.); b = color(p['hue'] + p['hue_spread'], .95, 1.)
        wash = a + np.clip(field, 0, 1)[..., None] * (b - a)
        shadows = np.clip(1 - np.max(out, axis=2), 0, 1) ** 2
        out += wash * (shadows * p['field'] * (.35 + field))[..., None]
    if p['reverse'] and (clock / p['reverse_period']) % 1 < .5:
        pivot = color(p['reverse_hue'], p['reverse_saturation'], 1.)
        out = out * (1 - p['reverse']) + np.maximum(0., pivot - out) * p['reverse']
    event = (clock / p['period'] + p['phase']) % 1
    gate = float(event < p['duration'] / p['period'])
    if p['static'] and (gate or p['band']):
        coarse = rng.random((max(2, round(h * .6)), max(2, round(w * .5)))).astype(np.float32)
        noise = np.asarray(Image.fromarray(coarse).resize((w, h), Image.Resampling.NEAREST))
        rows = rng.random((h, 1)).astype(np.float32)
        static = np.clip(noise * .8 + rows * .65 - .2, 0, 1)
        chroma = np.stack((np.roll(static, 2, 1), static, np.roll(static, -2, 1)), axis=2)
        center = ((clock * p['roll'] + .35) % 1) * 2 - 1
        band = np.clip(1 - np.abs(y - center) / max(.001, p['band']), 0, 1)
        amount = np.maximum(gate, band) * p['static']
        out = out * (1 - amount[..., None]) + chroma * amount[..., None]
    if p['curve']:
        # Inverse barrel map resamples every source and its finishing effects.
        sx = (x * (1 + p['curve'] * y*y) + 1) * w / 2 - .5
        sy = (y * (1 + p['curve'] * x*x) + 1) * h / 2 - .5
        ix = np.floor(sx).astype(int); iy = np.floor(sy).astype(int)
        fx = (sx - ix)[..., None]; fy = (sy - iy)[..., None]
        left = np.clip(ix, 0, w-1); right = np.clip(ix+1, 0, w-1)
        top = np.clip(iy, 0, h-1); bottom = np.clip(iy+1, 0, h-1)
        out = ((out[top, left] * (1-fx) + out[top, right] * fx) * (1-fy)
               + (out[bottom, left] * (1-fx) + out[bottom, right] * fx) * fy)
        edge = np.clip(np.minimum(1 - np.abs(sx * 2 / w - 1), 1 - np.abs(sy * 2 / h - 1)) * 60, 0, 1)
        out *= edge[..., None]
    out *= np.clip(1 - p['vignette'] * (x*x + y*y) / 2, 0, 1)[..., None]
    return arr * (1 - p['mix']) + out * p['mix']
