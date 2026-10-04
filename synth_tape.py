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


def _anchored_pull_shifts(width, displacement):
    """Monotonic horizontal stretch, with both canvas edges held in place.

    Map the source midpoint to 0.5 + displacement in each row. The inverse
    rational mapping uses only in-frame pixels: no tiling, flat edge extension,
    blanking or global zoom. Identity at zero and positive derivative throughout.
    """
    u = np.arange(width, dtype=np.float64)[None, :] / max(1, width - 1)
    d = np.clip(np.asarray(displacement)[:, None], -.42, .42)
    ratio = (.5 + d) / (.5 - d)
    source = u / (ratio + (1 - ratio) * u) * (width - 1)
    source[:, 0] = 0.
    source[:, -1] = width - 1
    return np.arange(width)[None, :] - source


def render_tape_damage(arr, p, time, speed, seed, *, pull_time=None):
    if p["mix"] == 0 or (not p.get("pull", 0) and not any(p[key] for key in ("tracking", "jitter", "dropouts", "chroma_delay", "bleed", "head_switch"))):
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
    if p.get("pull", 0):
        # Broad, irregular row delay. Continuous deterministic phases avoid
        # held random jumps and carry every detail of the combined picture.
        pull_time = time if pull_time is None else pull_time
        phase = (seed % 997) / 997 * math.tau
        center = .48 + .10 * math.sin(pull_time * speed * .73 + phase)
        profile = np.exp(-((y - center) / .30) ** 4)
        ripple = .82 + .12 * np.sin(y * 13 + pull_time * speed * .9 + phase) + .06 * np.sin(y * 31 - pull_time * speed * .4)
        displacement = p["pull"] * .42 * profile * ripple
        if p.get('pull_edges', 0) == 1:
            shifts = shift[:, None] + _anchored_pull_shifts(w, displacement)
        else:
            # Preserve the legacy operation order as well as its blanking.
            shifts = (shift + w * p['pull'] * .42 * profile * ripple)[:, None]
    else:
        shifts = shift[:, None]
    warped = _sample_rows(signal, shifts)

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
