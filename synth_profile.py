"""Solid head masks and reusable contour/scan treatments, evaluated at any time."""
from functools import lru_cache
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from synth_canvas import content_size, object_offset
from synth_particle_mesh import HEAD_MODELS, head_mesh
from synth_profile_v1 import _neck_dissolve


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


def _extends_canvas(p, preset, width, height, cw, ch):
    """A larger viewport reveals atmosphere without enlarging the object."""
    return bool(p.get('canvas_coverage', 1) and 'reference' in preset
                and (width > cw + .5 or height > ch + .5))


@lru_cache(maxsize=8)
def _projected_head(width, height, cw, ch, model, scale, yaw, pitch, roll, center_x, center_y, neck_length, neck_fullness, dx, dy, definition=0.):
    triangles, _, _ = head_mesh(HEAD_MODELS[int(model)])
    yaw, pitch, roll = map(math.radians, (yaw, pitch, roll))
    cy, sy = math.cos(yaw), math.sin(yaw); cx, sx = math.cos(pitch), math.sin(pitch)
    cz, sz = math.cos(roll), math.sin(roll)
    matrix = np.array(((cz, -sz, 0), (sz, cz, 0), (0, 0, 1))) @ np.array(((1, 0, 0), (0, cx, -sx), (0, sx, cx))) @ np.array(((cy, 0, sy), (0, 1, 0), (-sy, 0, cy)))
    vertices = triangles.copy()
    if definition:
        # Optional source geometry, before pose/projection. Soft feature weights
        # emphasize the facial profile without changing the skull or neck.
        front = np.clip((vertices[..., 2] - .5) / .35, 0, 1)
        center = np.exp(-(vertices[..., 0] / .25) ** 2)
        y = vertices[..., 1]
        relief = (.15 * np.exp(-((y + .32) / .12) ** 2)
                  + .025 * np.exp(-((y + .53) / .055) ** 2)
                  + .07 * np.exp(-((y + .82) / .15) ** 2))
        vertices[..., 2] += definition * front * center * relief
    fullness = neck_fullness * np.clip((-vertices[..., 1] - .92) / .2, 0, 1) * np.clip((vertices[..., 2] + .35) / .6, 0, 1)
    vertices[..., 2] += np.minimum(fullness, np.maximum(0, .65 - vertices[..., 2]))
    vertices[..., 1] -= np.clip((-vertices[..., 1] - 1.05) / .18, 0, 1) * neck_length
    points = vertices @ matrix.T
    xy = points[..., :2] * (ch * scale); xy[..., 1] *= -1
    xy[..., 0] += width / 2 + cw * (center_x - .5) + dx
    xy[..., 1] += height / 2 + ch * (center_y - .5) + dy
    mask = Image.new('L', (width, height)); draw = ImageDraw.Draw(mask)
    for polygon in xy:
        # Skip triangles wholly outside the viewport, retaining partial ones.
        if polygon[:, 0].max() < 0 or polygon[:, 0].min() >= width or polygon[:, 1].max() < 0 or polygon[:, 1].min() >= height: continue
        draw.polygon([tuple(point) for point in polygon], fill=255)
    # The mouth's internal mesh can leave tiny raster cracks in a solid cutout.
    mask = mask.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))
    result = np.asarray(mask, dtype=np.uint8)
    result.setflags(write=False)
    return result


def render_silhouette(arr, p, time, preset, seed):
    if p['opacity'] == 0: return arr
    h, w = arr.shape[:2]; cw, ch = content_size(preset, (w, h)); dx, dy = object_offset(preset, (w, h))
    pose = (cw, ch, p['model'], p['scale'], p['yaw'], p['pitch'], p['roll'], p['center_x'], p['center_y'], p['neck_length'], p['neck_fullness'], dx, dy, p.get('definition', 0.))
    mask = _projected_head(w, h, *(round(value, 6) for value in pose)).astype(np.float32) / 255
    if p['softness']: mask = _blur(mask, p['softness'] * ch / 540)
    return arr * (1 - mask[..., None] * p['opacity']) + mask[..., None] * p['opacity']


def render_edge_phosphor(arr, p, time, preset, seed, continuous_time=None):
    from synth_source_adapters import phosphor_inputs
    from synth_phosphor import render_phosphor
    source, context, region, softness = phosphor_inputs(arr, p, time, preset, seed, continuous_time)
    return render_phosphor(source, p, context, region, softness)


def render_scan_drag(arr, p, time, preset, seed):
    if p['mix'] == 0: return arr
    if not any(p[key] for key in ('amount', 'jitter', 'tearing', 'overload')) and p['window'] == 1: return arr
    h, w = arr.shape[:2]; cw, ch = content_size(preset, (w, h))
    extend = _extends_canvas(p, preset, w, h, cw, ch)
    rng = _rng(seed, time, preset['speed'], p['rate'])
    x = np.arange(w)[None, :]; y = (np.arange(h) + .5) / h
    # Broken fine rows plus one irregular overload region. Resampling stretches
    # actual contour colors; a blank signal never gains luminous bars.
    n = max(16, round(ch)); row = np.minimum((y * n).astype(int), n - 1)
    selected = (rng.random(n) < p['density']).astype(float)
    line = selected[row] * rng.uniform(.25, 1., n)[row]
    center = p['center'] + rng.uniform(-.025, .025) * p['wander']
    burst = np.exp(-((y - center) / max(.001, p['height'])) ** 6)
    lengths = rng.uniform(.35, 2.2, 300) * p['band_size'] / 270
    boundaries = np.cumsum(lengths)
    group = np.searchsorted(boundaries, y)
    groups = int(group.max()) + 1
    gains = rng.uniform(0., 1., groups)
    burst *= p['overload'] * np.where(gains[group] > .10, .4 + gains[group], 0.)
    activity = np.maximum(line * p['amount'], burst)
    shifts = (rng.normal(0., 1., n)[row] * p['jitter'] + rng.uniform(-1., 1., groups)[group] * burst * p['tearing']) * cw
    tracking_rng = _rng(seed + 31, time, preset['speed'], p['rate'] * .25)
    for i in range(p['blocks']):
        center = .055 + i * .11 + tracking_rng.uniform(-.025, .025)
        block = np.exp(-((y - center) / p['block_height']) ** 10)
        shifts += block * cw * p['tearing'] * tracking_rng.uniform(.25, 1.)
    # Peak detection is local to the source, so the tear follows Object X/Y.
    peak = np.argmax(arr.max(axis=2), axis=1)[:, None]
    distance = x - peak - shifts[:, None]
    direction = -1 if p['direction'] == 0 else 1
    stretch = 1 + activity[:, None] * p['length'] * 220
    source_x = peak + np.where(distance * direction >= 0, distance / stretch, distance)
    result = _sample(arr, source_x, extend=extend)
    if p['chroma']:
        chroma = p['chroma'] * cw * activity[:, None]
        result[..., 0] = _sample(arr[..., 0], source_x - chroma, extend=extend)
        result[..., 2] = _sample(arr[..., 2], source_x + chroma, extend=extend)
    highlight = result.max(axis=2)
    after_edge = np.clip(distance * direction / max(1., cw * .03), 0, 1)
    spectral = rng.uniform(0., 1., groups)[group]
    color = np.column_stack((.35 + spectral * .65, .95 - spectral * .65, np.ones(h)))
    result += np.maximum(0, highlight - .12)[..., None] * burst[:, None, None] * p['gain'] * color[:, None, :] * after_edge[..., None]
    result = np.minimum(result, 1.)
    noise = 1 - p['grain'] * activity[:, None] * rng.uniform(0., 1., (h, w))
    result *= noise[..., None]
    result = np.minimum(result, 1.) * (1 - np.minimum(1., burst)[:, None, None] * p['tint'] * (1 - color[:, None, :]))
    if p['softness']:
        result = np.stack([_blur(result[..., channel], p['softness'] * cw / 480) for channel in range(3)], axis=-1)
    if p['glow'] and p['overload']:
        halo = np.stack([_blur(result[..., channel], cw * .018) for channel in range(3)], axis=-1)
        result += halo * p['glow'] * np.minimum(1., burst)[:, None, None] * (1 - np.minimum(result, 1.))
    result *= (1 - p['dropout'] * (rng.random(n)[row] < .12))[:, None, None]
    if p['window'] < 1 and not extend:
        gate = np.clip((cw * p['window'] / 2 - np.abs(x - w / 2)) / max(1., cw * .003), 0, 1)
        result *= gate[..., None]
    return arr * (1 - p['mix']) + result * p['mix']
