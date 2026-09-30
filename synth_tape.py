"""Stateless tape faults that resample the source, never draw luminous shapes."""
import math

import numpy as np


def _sample_rows(signal, shifts):
    """Subpixel horizontal delay with blanking instead of wraparound."""
    h, w = signal.shape[:2]
    x = np.arange(w)[None, :] - np.asarray(shifts)
    left = np.floor(x).astype(int)
    fraction = x - left
    y = np.arange(h)[:, None]
    a = signal[y, np.clip(left, 0, w - 1)]
    b = signal[y, np.clip(left + 1, 0, w - 1)]
    result = a * (1 - fraction[..., None]) + b * fraction[..., None]
    return result * ((x >= 0) & (x <= w - 1))[..., None]


def render_tape_damage(arr, p, time, speed, seed):
    if p["mix"] == 0 or not any(p[key] for key in ("tracking", "jitter", "dropouts", "chroma_delay", "bleed", "head_switch")):
        return arr
    h, w = arr.shape[:2]
    tick = math.floor(time * speed * p["rate"] + 1e-9)
    rng = np.random.default_rng(np.random.SeedSequence((seed, tick & 0xffffffffffffffff)))
    y = (np.arange(h) + .5) / h
    x = (np.arange(w) + .5) / w
    background = np.array((.055, .067, .055), dtype=np.float32)
    signal = arr - background

    # A small, irregular region loses horizontal lock. It moves the image
    # itself, including its texture, without adding an independent bright bar.
    centers = rng.uniform(.08, .90, 2)
    widths = rng.uniform(.008, .035, 2)
    offsets = rng.uniform(-1., 1., 2)
    tracking = sum(offset * np.exp(-((y - center) / width) ** 6)
                   for center, width, offset in zip(centers, widths, offsets))
    scan_rows = np.minimum((y * 576).astype(int), 575)
    jitter = rng.normal(0., 1., 576)[scan_rows]
    bottom = np.clip((y - .92) / .08, 0., 1.)
    switch = bottom ** 2 * np.sin(y * 180 + tick * 1.7) * .055
    shift = w * (p["tracking"] * tracking + p["jitter"] * jitter + p["head_switch"] * switch)
    warped = _sample_rows(signal, shift[:, None])

    # Delay and low-pass the chroma while retaining the sharper luminance.
    luminance = warped @ np.array((.299, .587, .114))
    chroma = warped - luminance[..., None]
    delay = w * p["chroma_delay"] * (1 + .15 * math.sin(tick * .71))
    spread = w * p["bleed"]
    chroma = (_sample_rows(chroma, delay) * .55
              + _sample_rows(chroma, delay + spread * .5) * .3
              + _sample_rows(chroma, delay + spread) * .15)
    treated = luminance[..., None] + chroma

    # Short missing stretches of scanline, rather than full-frame rectangles.
    loss = np.zeros((h, w))
    for center, start, length, thickness in rng.uniform(0., 1., (8, 4)):
        row = np.exp(-((y - center) / (.0015 + .0025 * thickness)) ** 4)
        segment = np.clip((x - start * .8) / .015, 0., 1.) * np.clip((start * .8 + .08 + length * .35 - x) / .04, 0., 1.)
        loss = np.maximum(loss, row[:, None] * segment[None, :])
    treated *= (1 - p["dropouts"] * loss * .95)[..., None]
    treated *= (1 - p["head_switch"] * bottom[:, None, None] * .25)
    return arr * (1 - p["mix"]) + (background + treated) * p["mix"]
