"""Animated polar gradient meshes. Each spoke carries vector stops in artwork space."""
from __future__ import annotations

import colorsys
from functools import lru_cache
import json
import math

import numpy as np
from PIL import Image, ImageFilter

from nebula.sources.synth_radial_gradients import STOP_KEYS, CHANNELS

RADIUS_UNITS = 4096
MAX_DESIGN_BYTES = 4_000_000
PULSE_FRACTION = .18  # Fraction of the next pass during which both sets of rays are visible.
DESIGN_CONTROLS = frozenset(('fold_design', 'core_scale', 'ray_scale', 'aperture_scale',
                             'ray_sharpness', 'fan_width', 'fold_repeat'))
SHARED_CONTROLS = frozenset(('pattern', 'expansion', 'center_x', 'center_y', 'orientation',
                             'petals', 'cycle', 'direction', 'motion_phase', 'rotation',
                             'light', 'softness'))


def parameters(P):
    yield P('fold_design', 'Gradient design', '', kind='polar',
            hint='Embedded vector gradient. Each pose moves the stops on the same set of mirrored spokes.')
    yield P('fold_repeat', 'After last pose', 0, 0, 1, 1,
            'Choose how the next pass begins. Outward pulse opens the next set of rays from the center, at the current travel tempo.',
            choices=('Reverse path', 'Outward pulse'))
    yield P('core_scale', 'Center size', 1., .1, 3., .01, 'Scale the central region inside each ray.')
    yield P('ray_scale', 'Ray length', 1., .15, 3., .01, 'Stretch the rays between the center and the aperture.')
    yield P('aperture_scale', 'Aperture size', 1., .15, 3., .01, 'Adjust the width of the surrounding facets.')
    yield P('ray_sharpness', 'Ray sharpness', 1., .25, 3., .01, 'Pinch or broaden the tip of each reflected ray.')
    yield P('fan_width', 'Side fan width', 1., .1, 2.8, .01, 'Widen or narrow the opposing horizontal sectors.')


def default_design():
    # A small neutral example makes the source usable in an empty composition.
    inks = [[round(v * 255) for v in colorsys.hsv_to_rgb(i / 8, .55, .85)] for i in range(8)]
    poses = []
    for phase in (0., 1.):
        wedges = []
        for sector in range(8):
            guides = []
            for j in range(3):
                tip = (j / 2 if sector % 2 else 1 - j / 2)
                ray = round(450 + (1450 + 1050 * phase) * tip ** 2)
                positions = (0, 150 + 120 * phase, ray, ray + 140, 3300 + 150 * tip, 4500)
                guides.append([[round(r), *inks[i]] for r, i in zip(positions, (2, 2, 5, 6, 0, 3))])
            wedges.append(guides)
        poses.append(dict(at=phase, wedges=wedges))
    return dict(version=1, inks=inks, bands=[1, 2, 4], poses=poses)


@lru_cache(maxsize=4)
def decode_design(value):
    if not isinstance(value, str) or len(value) > MAX_DESIGN_BYTES:
        raise ValueError('The gradient design exceeds the supported size.')
    try:
        data = json.loads(value) if value else default_design()
        if data['version'] != 1 or not 1 <= len(data['poses']) <= 64:
            raise ValueError
        inks = np.asarray(data['inks'], dtype=np.float32)
        times = np.asarray([p['at'] for p in data['poses']], dtype=np.float64)
        stops = np.asarray([p['wedges'] for p in data['poses']], dtype=np.float32)
        bands = tuple(data['bands'])
        if (stops.ndim != 5 or stops.shape[-1] != 4 or not 3 <= stops.shape[1] <= 48
                or not 2 <= stops.shape[2] <= 32 or not 5 <= stops.shape[3] <= 64
                or inks.shape != (8, 3) or len(bands) != 3 or any(type(b) is not int for b in bands)
                or not 0 < bands[0] < bands[1] < bands[2] < stops.shape[3] - 1
                or times[0] != 0 or (len(times) > 1 and times[-1] != 1)
                or not np.isfinite(times).all() or np.any(np.diff(times) <= 0)):
            raise ValueError
        radii, colors = stops[..., 0], stops[..., 1:]
        if (not np.isfinite(stops).all() or not np.isfinite(inks).all()
                or inks.min() < 0 or inks.max() > 255 or colors.min() < 0 or colors.max() > 255
                or np.any(radii[..., 0] != 0) or np.any(np.diff(radii, axis=-1) <= 0)
                or radii.max() > 8 * RADIUS_UNITS):
            raise ValueError
    except (KeyError, IndexError, TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise ValueError('Invalid polar gradient. Check the poses, ordered radial stops, eight inks and three band indices.') from exc
    stops[..., 0] /= RADIUS_UNITS
    return times, stops, inks, bands


def validate_design(value):
    if not isinstance(value, str):
        raise ValueError('The polar gradient must be embedded in the project.')
    decode_design(value)
    return value


def pose_position(p, seconds):
    sign = (1, -1, 0)[int(p['direction'])]
    start = 1 - p['motion_phase'] if sign < 0 else p['motion_phase']
    t = (start + sign * seconds / p['cycle']) % 2
    return 1 - abs(1 - t)


def _pose_at(p, t):
    times, poses, inks, bands = decode_design(p['fold_design'])
    right = min(len(times) - 1, int(np.searchsorted(times, t, side='right')))
    left = max(0, right - 1)
    f = (t - times[left]) / (times[right] - times[left]) if right != left else 0.
    stops = poses[left] + np.float32(f) * (poses[right] - poses[left])
    distances = np.diff(stops[..., 0], axis=-1)
    core, ray, aperture = bands
    distances[..., :core] *= p['core_scale']
    distances[..., core:ray] *= p['ray_scale']
    distances[..., ray:aperture] *= p['aperture_scale']
    stops[..., 1:, 0] = np.cumsum(distances, axis=-1)
    target = np.asarray([colorsys.hsv_to_rgb(*(p[key + '_' + c] for c in CHANNELS))
                         for key in STOP_KEYS], dtype=np.float32) * 255
    if not np.allclose(inks, target, atol=.01):
        rgb = stops[..., 1:]
        delta = rgb[..., None, :] - inks
        weights = 1 / np.maximum(np.sum(delta * delta, axis=-1), .01) ** 2
        weights /= np.sum(weights, axis=-1, keepdims=True)
        rgb += weights @ (target - inks)
    return stops


def _moving_stops(p, seconds):
    travel = p['motion_phase'] + seconds / p['cycle']
    if (not p.get('fold_repeat') or p['direction'] == 2 or travel <= 1
            or len(decode_design(p['fold_design'])[0]) == 1):
        return _pose_at(p, pose_position(p, seconds)), None, 0.

    phase = travel % 1
    forward = p['direction'] == 0
    end = 1. if forward else 0.
    if phase == 0:
        return _pose_at(p, end), None, 0.
    incoming = _pose_at(p, phase if forward else 1 - phase)
    if phase >= PULSE_FRACTION:
        return incoming, None, 0.

    # Keep the previous rays travelling out while their successors open in
    # the center. Each pass uses the same clock, even after a direct seek.
    pulse = phase / PULSE_FRACTION
    outgoing = _pose_at(p, end)
    outgoing[..., 0] *= 1 + pulse
    incoming[..., 0] *= 1 - .5 * (1 - pulse) ** 2
    return incoming, outgoing, pulse


def _fill_gradient(table, stops, radii, rows, mix=None):
    guides = stops.shape[1]
    for i in range(rows + 1):
        u = i / rows * (guides - 1)
        left = min(int(u), guides - 2)
        section = stops[:, left] + (u - left) * (stops[:, left + 1] - stops[:, left])
        for wedge, knots in enumerate(section):
            line = table[wedge * (rows + 1) + i]
            for channel in range(3):
                values = np.interp(radii, knots[:, 0], knots[:, channel + 1])
                if mix is None:
                    line[:, channel] = values
                else:
                    line[:, channel] += mix * (values - line[:, channel])


def _gradient_table(stops, scale, outgoing, pulse):
    wedges = len(stops)
    # Adjacent wedges have separate edge colors at a fold. Both passes use
    # the same radial grid, so the transition works at any preview or export size.
    rows = min(192, max(16, math.ceil(scale * math.pi / wedges / 2)))
    extent = float(stops[..., -1, 0].max())
    if outgoing is not None:
        extent = max(extent, float(outgoing[..., -1, 0].max()))
    columns = min(4096, max(32, math.ceil(extent * scale) + 1))
    radii = np.linspace(0, extent, columns, dtype=np.float32)
    table = np.empty((wedges * (rows + 1), columns, 3), np.float32)
    mix = None
    if outgoing is not None:
        _fill_gradient(table, outgoing, radii, rows)
        feather = .46
        front = np.clip((pulse * (1 + feather) - radii / extent) / feather, 0, 1)
        mix = front * front * (3 - 2 * front)
    _fill_gradient(table, stops, radii, rows, mix)
    return table, rows, (columns - 1) / extent


def render_folded(p, size, center, unit, seconds):
    w, h = size
    scale = max(.01, unit * p['expansion'])
    stops, outgoing, pulse = _moving_stops(p, seconds)
    source_count = len(stops)
    count = int(p['petals'])
    table, rows, columns_per_unit = _gradient_table(stops, scale, outgoing, pulse)
    # Match the nearest authored sector with the same tip/valley orientation.
    source_wedges = np.arange(source_count)
    lookup = [min(source_wedges[j % 2::2], key=lambda k: abs((k + .5) / source_count - (j + .5) / count))
              for j in range(count)]
    lookup = np.asarray(lookup, dtype=np.intp)
    angle = math.radians((p['orientation'] + p['rotation'] * seconds) % 360)
    co, si = math.cos(angle), math.sin(angle)
    x = np.arange(w, dtype=np.float32)[None, :] + .5 - center[0]
    result = np.empty((h, w, 3), dtype=np.float32)
    fan = 1 / count
    width = min(.49, p['fan_width'] * fan)
    for top in range(0, h, 128):
        y = np.arange(top, min(h, top + 128), dtype=np.float32)[:, None] + .5 - center[1]
        across = np.abs(x * co + y * si)
        down = y * co - x * si
        a = np.arctan2(across, -down) / np.pi
        if p['fan_width'] != 1:
            offset = a - .5
            a = .5 + np.sign(offset) * np.interp(np.abs(offset), [0, width, .5], [0, fan, .5])
        sector = np.minimum((a * count).astype(np.intp), count - 1)
        local = np.clip(a * count - sector, 0, 1)
        if p['ray_sharpness'] != 1:
            odd = (sector % 2 != 0)
            from_tip = np.where(odd, 1 - local, local) ** (1 / p['ray_sharpness'])
            local = np.where(odd, 1 - from_tip, from_tip)
        row = local * rows
        lo = np.minimum(row.astype(np.intp), rows - 1)
        row_mix = (row - lo)[..., None].astype(np.float32)
        lo += lookup[sector] * (rows + 1)
        r = np.minimum(np.hypot(x, y) * (columns_per_unit / scale), table.shape[1] - 1)
        col = np.minimum(r.astype(np.intp), table.shape[1] - 2)
        radial_mix = (r - col)[..., None].astype(np.float32)
        first = table[lo, col] * (1 - radial_mix) + table[lo, col + 1] * radial_mix
        last = table[lo + 1, col] * (1 - radial_mix) + table[lo + 1, col + 1] * radial_mix
        result[top:top + len(y)] = first + (last - first) * row_mix
    result = np.clip(result * (p['light'] / 255), 0, 1)
    if p['softness'] > 0:
        image = Image.fromarray(np.uint8(result * 255))
        result = np.asarray(image.filter(ImageFilter.GaussianBlur(p['softness'] * unit / 720)), dtype=np.float32) / 255
    return result
