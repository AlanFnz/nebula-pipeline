"""Held, deterministic registration of the source before finishing effects."""
import math

import numpy as np


def frame_pose(p, time, speed, seed):
    """Bounded per-frame poses; never accumulate drift or need earlier frames."""
    tick = math.floor(time * speed * p['rate'] + 1e-8)
    rng = np.random.default_rng(np.random.SeedSequence((int(seed), int(p['seed']), tick & 0xffffffffffffffff)))
    x, y, angle, zoom = rng.uniform(-1., 1., 4) * p['strength']
    return x * p['x'], y * p['y'], angle * p['rotation'], 1 + zoom * p['scale'] / 100


def render_frame_jitter(arr, p, time, speed, seed):
    if p['strength'] == 0 or not any(p[key] for key in ('x', 'y', 'rotation', 'scale')):
        return arr
    h, w = arr.shape[:2]
    dx, dy, angle, zoom = frame_pose(p, time, speed, seed)
    # The short edge gives the same displacement relative to the artwork when
    # previewing, exporting or changing between portrait and landscape canvases.
    dx *= min(w, h) / 720; dy *= min(w, h) / 720
    angle = math.radians(angle)
    y, x = np.mgrid[:h, :w].astype(np.float32)
    cx, cy = (w - 1) / 2, (h - 1) / 2
    x = (x - cx - dx) / zoom; y = (y - cy - dy) / zoom
    src_x = np.clip(x * math.cos(angle) + y * math.sin(angle) + cx, 0, w - 1)
    src_y = np.clip(-x * math.sin(angle) + y * math.cos(angle) + cy, 0, h - 1)
    left = np.floor(src_x).astype(int); top = np.floor(src_y).astype(int)
    right = np.minimum(left + 1, w - 1); bottom = np.minimum(top + 1, h - 1)
    fx = (src_x - left).astype(np.float32)[..., None]
    fy = (src_y - top).astype(np.float32)[..., None]
    # Subpixel sampling retains subtle motion in small previews and preserves
    # highlight values above 1. Boundaries extend edge pixels, never wrap tiles.
    upper = arr[top, left] * (1 - fx) + arr[top, right] * fx
    lower = arr[bottom, left] * (1 - fx) + arr[bottom, right] * fx
    return upper * (1 - fy) + lower * fy
