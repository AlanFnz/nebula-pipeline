"""Looping optical bead planes, projected analytically without external media.

The two vanishing directions come from a rectangular projective lattice.
Emitters keep a lens-like footprint instead of flattening into the plane.
Component-wise maximum models overlapping exposures without blowing out the
far rows; warm/cool defocus and a foreground light rail complete the image.
"""
from __future__ import annotations

import colorsys
import math
import numpy as np
from PIL import Image, ImageFilter

from synth_canvas import content_size, object_offset


def modules(Module, P):
    return (Module('spectral_tunnel', 'Spectral tunnel',
        'Two luminous perspective planes, a bright center rail and a seamless optical ripple.', (
        P('shape', 'Light shape', 0, 0, 3, 1, choices=('Ellipse', 'Square', 'Diamond', 'Polygon')),
        P('sides', 'Polygon sides', 6, 3, 12, 1),
        P('size', 'Light size', 1.1, .3, 2., .01),
        P('aspect', 'Light height', .52, .25, 1.5, .01),
        P('rows', 'Rows per plane', 24, 6, 60, 1),
        P('spacing', 'Row spacing', 4., 2., 8., .1),
        P('vanishing_x', 'Vanishing point X', 1.26, .65, 2., .01, 'Relative to the artwork width. Values above 1 place it beyond the right edge.'),
        P('cross_x', 'Cross perspective X', .256, -.5, .8, .01),
        P('horizon', 'Horizon height', .57, .2, .8, .01),
        P('depth', 'Plane spread', 1., .5, 2., .01),
        P('gap', 'Horizon gap', .05, 0., .15, .005),
        P('rail', 'Center light rail', 1., 0., 1., .01),
        P('period', 'Loop period', .3, .1, 20., .01, 'Seconds per complete motion and texture cycle at global speed 1.'),
        P('motion', 'Motion', 0, 0, 1, 1, choices=('Optical ripple', 'Traveling lights')),
        P('amplitude', 'Ripple amount', .12, 0., .8, .01),
        P('phase', 'Starting phase', 0., 0., 1., .01),
        P('direction', 'Direction', 0, 0, 1, 1, choices=('Forward', 'Reverse')),
        P('cadence', 'Frames per loop', 10, 0, 120, 1, 'Zero gives continuous motion. Ten preserves the reference GIF cadence.'),
        P('warm_hue', 'Warm halo hue', .065, 0., 1., .01),
        P('cool_hue', 'Cool halo hue', .60, 0., 1., .01),
        P('saturation', 'Halo saturation', .98, 0., 1., .01),
        P('light', 'Brightness', 1., 0., 2., .01),
        P('glow', 'Halo strength', 1., 0., 2., .01),
        P('spread', 'Halo spread', 1., .3, 2., .01),
        P('softness', 'Optical softness', 1.8, 0., 5., .05, 'Pixels at a 500-pixel artwork edge.'),
        P('grain', 'Fine grain', .019, 0., .08, .001),
        P('mix', 'Mix', 1., 0., 1., .01),
    )),)


def loop_phase(seconds, p, speed=1.):
    phase = round((seconds * speed / p['period'] + p['phase']) % 1., 10) % 1.
    if p['cadence']:
        phase = math.floor(phase * p['cadence'] + 1e-8) / p['cadence']
    return phase


def _distance(u, v, shape, sides):
    if shape == 1:
        return np.maximum(np.abs(u), np.abs(v))
    if shape == 2:
        return np.abs(u) + np.abs(v)
    if shape == 3:
        angle = np.arctan2(v, u)
        sector = 2 * np.pi / sides
        return np.hypot(u, v) * np.cos((angle + sector / 2) % sector - sector / 2)
    return np.hypot(u, v)


def render_spectral_tunnel(arr, p, seconds, preset):
    if p['mix'] <= 0:
        return arr
    h, w = arr.shape[:2]
    cw, ch = content_size(preset, (w, h))
    unit = max(1., min(cw, ch)) / 500.
    dx, dy = object_offset(preset, (w, h))
    ox, oy = w / 2 - 250 * unit + dx, h / 2 - 250 * unit + dy
    phase = loop_phase(seconds, p, preset.get('speed', 1.))
    direction = 1 if p['direction'] == 0 else -1
    # This reference shimmers back and forth; it does not advance a whole cell.
    travel = (p['amplitude'] * (math.sin(math.tau * phase) +
              .12 * math.sin(2 * math.tau * phase))) if p['motion'] == 0 else phase
    travel *= direction
    vx, cross = p['vanishing_x'] * 500, p['cross_x'] * 500
    horizon, depth = p['horizon'] * 500, 2091 * p['depth']
    warm = np.asarray(colorsys.hsv_to_rgb(p['warm_hue'], p['saturation'], 1.), np.float32)
    cool = np.asarray(colorsys.hsv_to_rgb(p['cool_hue'], p['saturation'], .8), np.float32)
    core_color = np.asarray((.70, 1., .80), np.float32)
    white = np.asarray((.94, 1., .90), np.float32)
    out = np.zeros_like(arr, dtype=np.float32)
    yy, xx = np.mgrid[:h, :w].astype(np.float32)
    # Bounds encompass every visible column including the widest supported halo.
    ii, jj = np.meshgrid(np.arange(-1, int(p['rows']) - 1), np.arange(-500, 700))
    ii, jj = ii.ravel(), jj.ravel()
    for plane in range(3):
        layer = np.zeros_like(out)
        if plane == 2 and p['rail'] <= 0:
            continue
        if plane == 2:
            i, j = np.zeros(1200), np.arange(-500, 700) - travel
        else:
            i, j = ii + .77 * plane, jj - 1.09 * plane - travel
        d = j + p['spacing'] * i + 9
        valid = d > 1.5
        d, i, j = d[valid], i[valid], j[valid]
        x = (vx * j + cross * p['spacing'] * i + 531) / d
        y = horizon + (-1 if plane == 0 else 1) * depth / d
        r = 205 * p['size'] / d
        slope = (y - horizon) / np.minimum(-1., x - vx) * .65
        if plane == 2:
            y = np.full_like(x, horizon + 5)
            r = 350 * p['size'] / d
            y += 45 / d * np.sin(j * 2.1 + math.tau * phase)
            slope = np.zeros_like(x)
        x, y, r = x * unit + ox, y * unit + oy, r * unit
        reach = 5 * p['spread'] * max(1., p['aspect']) + 2
        valid = (x + reach*r > 0) & (x - reach*r < w) & (y + reach*r > 0) & (y - reach*r < h)
        for x, y, r, sl in zip(x[valid], y[valid], r[valid], slope[valid]):
            x0, x1 = max(0, int(x - reach*r)), min(w, int(x + reach*r) + 2)
            y0, y1 = max(0, int(y - reach*r)), min(h, int(y + reach*r) + 2)
            if x0 >= x1 or y0 >= y1:
                continue
            u = (xx[y0:y1, x0:x1] - x) / r
            v = (yy[y0:y1, x0:x1] - y - sl*(xx[y0:y1, x0:x1] - x)) / (r*p['aspect'])
            dist = _distance(u, v, p['shape'], p['sides'])
            core = np.exp(-2 * dist**4) * 1.65
            warm_blur = np.exp(-2 * (u*u + ((v + .8)/1.25)**2) / (1.9*p['spread'])**2) * 1.25
            cool_blur = np.exp(-2 * (u*u + ((v - 1.05)/1.4)**2) / (2.6*p['spread'])**2) * .8
            light = core[..., None] * core_color + p['glow'] * (warm_blur[..., None] * warm + cool_blur[..., None] * cool)
            attenuation = .74 + .26 * min(1., r / (12*unit))
            if plane == 2:
                light = core[..., None] * np.asarray((1., 1.05, 1.), np.float32) + p['glow'] * (warm_blur[..., None] * warm * 1.4 + cool_blur[..., None] * cool * 2.8)
            light = attenuation * np.minimum(1. if plane == 2 else white, light)
            if plane == 2:
                light *= p['rail']
            np.maximum(layer[y0:y1, x0:x1], light, out=layer[y0:y1, x0:x1])
        if plane < 2:
            boundary = (horizon + (-1 if plane == 0 else 1) * 500*p['gap']) * unit + oy
            distance = (boundary - yy) if plane == 0 else (yy - boundary)
            layer *= np.clip(distance / max(1., 2*unit) + .5, 0., 1.)[..., None]
            np.maximum(out, layer, out=out)
        else:
            rail_width = np.maximum(2*unit, 55*unit*(1-(xx-ox)/(max(vx, 501)*unit))) * p['size']
            alpha = np.exp(-.5 * np.minimum(10., np.abs((yy-oy-(horizon+5)*unit)/rail_width))**8)[..., None]
            out = out*(1-alpha*p['rail']) + layer*alpha
    out = np.clip(out * p['light'], 0, 1)
    if p['softness']:
        out = np.asarray(Image.fromarray(np.uint8(out*255)).filter(
            ImageFilter.GaussianBlur(p['softness']*unit)), np.float32) / 255.
    if p['grain']:
        # The texture is periodic too, independent of playback/seek history.
        rng = np.random.default_rng(int(preset.get('seed', 0)) + round(phase*100000))
        out += rng.normal(0, p['grain'], (h, w, 1)).astype(np.float32) * np.sqrt(out)
    return arr * (1 - p['mix']) + np.clip(out, 0, 1) * p['mix']
