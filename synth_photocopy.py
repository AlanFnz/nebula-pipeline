"""Deterministic toner, screened ink and uneven copy exposure for any image."""
from __future__ import annotations

import math
import numpy as np
from PIL import Image, ImageFilter


def _noise(rng, width, height, cell):
    field = rng.standard_normal((max(2, math.ceil(height / cell)), max(2, math.ceil(width / cell)))).astype(np.float32)
    field = np.asarray(Image.fromarray(field).resize((width, height), Image.Resampling.BICUBIC), dtype=np.float32)
    return field / max(float(field.std()), 1e-6)


def render_photocopy(arr, p, time, seed):
    if p['mix'] == 0: return arr
    h, w = arr.shape[:2]
    scale = min(w, h) / 720
    tick = math.floor(time * p['cadence'] + 1e-8)
    rng = np.random.default_rng(np.random.SeedSequence([int(seed), 913, tick & 0xffffffff]))
    grain = _noise(rng, w, h, max(.6, p['grain_size'] * scale))
    clumps = _noise(rng, w, h, max(3., 18 * scale))
    fine = rng.standard_normal((h, w)).astype(np.float32)
    luma = arr @ np.array((.2126, .7152, .0722), dtype=np.float32)
    if p['softness']:
        luma = np.asarray(Image.fromarray(np.uint8(np.clip(luma * 255, 0, 255))).filter(ImageFilter.GaussianBlur(p['softness'] * scale)), dtype=np.float32) / 255
    if p['edge_wear']:
        yy, xx = np.mgrid[:h, :w].astype(np.float32)
        dx = (grain + clumps * .5) * p['edge_wear'] * scale
        sx = np.clip(xx + dx, 0, w - 1); sy = np.clip(yy - dx * .7, 0, h - 1)
        left = sx.astype(int); top = sy.astype(int)
        right = np.minimum(left + 1, w - 1); bottom = np.minimum(top + 1, h - 1)
        fx = sx - left; fy = sy - top
        luma = (luma[top, left] * (1 - fx) + luma[top, right] * fx) * (1 - fy) + (luma[bottom, left] * (1 - fx) + luma[bottom, right] * fx) * fy
    # Copy contrast is independent from exposure: black figures retain their
    # outline as the illumination and toner density change behind them.
    ink = np.clip((luma - p['threshold']) * p['contrast'] + .5, 0, 1)
    ink = ink * (1 - p['invert']) + (1 - ink) * p['invert']
    yy, xx = np.mgrid[:h, :w].astype(np.float32)
    x = (xx - w * p['light_x']) / min(w, h)
    y = (yy - h * .5) / min(w, h)
    phase = time / p['period'] + p['phase']
    drift = p['light_drift'] * math.sin(phase * math.tau)
    spread = max(.05, p['light_width'])
    beams = np.exp(-((x + .3 + drift) / spread) ** 2)
    beams += .75 * np.exp(-((x - .32 + drift * .5) / (spread * .45)) ** 2)
    floor = np.exp(-((y - (h / min(w, h)) * .43) / .12) ** 2)
    horizon = 1 - .65 * np.exp(-((yy / h - .81) / .13) ** 2)
    field = np.clip(.15 + beams * .7 * horizon + floor * .65, .05, 1.15)
    light = 1 - p['light_depth'] + field * p['light_depth']
    held = (phase % 1.)
    dark = 1 - p['blackout'] if .40 <= held < .58 else 1.
    exposure = 2 ** (p['exposure'] + rng.uniform(-1, 1) * p['flutter']) * dark
    tone = ink * light * exposure
    # The screen is a continuous angled dot lattice. Its ink coverage follows
    # the image; it is not a rectangular texture pasted over the composition.
    angle = math.radians(p['screen_angle'])
    pitch = max(1., p['dot_size'] * scale)
    u = (xx * math.cos(angle) + yy * math.sin(angle)) / pitch
    v = (-xx * math.sin(angle) + yy * math.cos(angle)) / pitch
    dots = (np.cos(u * math.tau) + np.cos(v * math.tau)) * .5
    screen = np.clip((tone - .48 + dots * .42) * 6 + .5, 0, 1)
    screened = tone * (1 - p['halftone']) + screen * p['halftone']
    # Fresh, multi-scale toner every scan; darkest ink retains fine paper tooth.
    etched = np.clip((screened + (grain * .24 + clumps * .055) * p['grain'] - .35) * 2.1, 0, 1)
    etched += fine * .027 * p['grain'] + np.maximum(grain - 1., 0) * .017 * p['grain']
    etched = np.clip(etched, 0, 1)
    cold = p['tint'] * (1 - p['tint_drift'] + p['tint_drift'] * abs(math.sin(phase * math.tau)))
    # White highlights, cyan mids, blue dark mids; deepest black stays neutral.
    color = np.array((1 - .36 * cold, 1 - .10 * cold, 1.), dtype=np.float32)
    result = p['black'] + etched[..., None] * (p['white'] - p['black']) * color
    return arr * (1 - p['mix']) + result * p['mix']
