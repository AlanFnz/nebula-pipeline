"""Nested gradient discs. Each copy has its own rotated material coordinates."""
from __future__ import annotations

import colorsys
from functools import lru_cache
import math

import numpy as np
from PIL import Image, ImageFilter

STOP_COUNT = 8
CHANNELS = ('hue', 'saturation', 'light')
STOP_KEYS = tuple(f'stop_{i}' for i in range(1, STOP_COUNT + 1))


CROWN_ONLY = frozenset(('petals', 'detail', 'branching', 'flow', 'variation', 'phase',
                        'center_drift', 'drift_speed', 'palette', 'color_speed', 'grain',
                        'vibration', 'vibration_speed', 'vibration_wavelength', 'vibration_irregularity'))
SHARED = frozenset(('pattern', 'expansion', 'rotation', 'color_phase', 'light', 'softness'))


def travel(p, seconds):
    phase = (seconds/p['motion_period'] + p['motion_phase']) % 1
    position = .5 - .5*math.cos(2*math.pi*phase)
    return position + p['motion_ease']*math.sin(2*math.pi*position)/(2*math.pi)


def gradient_parameters(P):
    yield P('pattern', 'Pattern', 0, 0, 1, 1, choices=('Branching crowns', 'Nested gradients'))
    yield P('copies', 'Disc count', 14, 1, 48, 1)
    yield P('copy_scale', 'Scale per copy', .80, .45, .98, .001, 'Radius of each disc relative to the one beneath it.')
    yield P('copy_angle', 'Turn per copy', 12., -180, 180, .1, 'Degrees of rotation between neighboring discs.')
    yield P('center_x', 'Spiral center X', 0., -3, 3, .01, 'Offset from canvas center in units of the shorter artwork edge. Positive moves right.')
    yield P('center_y', 'Spiral center Y', 0., -3, 3, .01, 'Offset from canvas center in units of the shorter artwork edge. Positive moves down.')
    yield P('disc_x', 'Disc offset X', .12, -1, 1, .01, 'Offset of each disc from the spiral pivot, in disc radii.')
    yield P('disc_y', 'Disc offset Y', .18, -1, 1, .01)
    yield P('orientation', 'Starting angle', 0., -180, 180, .1)
    yield P('focus_x', 'Gradient focus X', .4, -8, 8, .01, 'Position of the gradient inside each disc, in disc radii.')
    yield P('focus_y', 'Gradient focus Y', .3, -8, 8, .01)
    yield P('spread', 'Gradient spread', .65, -3, 3, .001, 'Palette cycles per disc radius.')
    yield P('cycle', 'Color cycle (s)', 8., .25, 120, .01, 'Seconds per turn of the palette at normal speed.')
    yield P('direction', 'Color direction', 0, 0, 2, 1, choices=('Forward', 'Reverse', 'Hold'))
    yield P('pace_swing', 'Cycle easing', 0., 0, 1, .01, 'Vary the speed within each color cycle.')
    yield P('ease_phase', 'Easing phase', 0., 0, 1, .01)
    yield P('falloff', 'Gradient falloff', 1., .2, 3, .01, 'Shape the transition from the focus to the rim.')
    yield P('motion_period', 'Disc cycle (s)', 8., .25, 120, .01, 'Time to reach the other pose and return.')
    yield P('motion_ease', 'Disc easing', 0., -1, 1, .01, 'Adjust the acceleration between the two poses.')
    yield P('motion_phase', 'Disc phase', 0., 0, 1, .001)
    yield P('pan_x', 'Center travel X', 0., -3, 3, .001, 'Horizontal distance from the starting center to its farthest point, in artwork edges.')
    yield P('pan_y', 'Center travel Y', 0., -3, 3, .001)
    yield P('disc_travel_x', 'Disc travel X', 0., -2, 2, .001, 'Horizontal travel in each disc’s own rotated coordinates, in radii.')
    yield P('disc_travel_y', 'Disc travel Y', 0., -2, 2, .001)
    yield P('diffusion', 'Radial diffusion', .04, 0, .4, .001, 'Softens disc boundaries along rays from the center of the artwork.')
    yield P('lens_x', 'Diffusion center X', 0., -3, 3, .01, 'Lens origin relative to the canvas center, in shorter artwork edges.')
    yield P('lens_y', 'Diffusion center Y', 0., -3, 3, .01)
    for index, key in enumerate(STOP_KEYS):
        yield P(key+'_position', f'Color {index+1} position', index/STOP_COUNT, 0, 1, .001, 'Position on the repeating palette. Coincident stops use the last color.')
        for channel, value in zip(CHANNELS, (index / STOP_COUNT, .55, .85)):
            yield P(key + '_' + channel, f'Color {index + 1} {channel}', value, 0, 1, .001)


@lru_cache(maxsize=16)
def _ramp(swatches):
    """Periodic cubic interpolation keeps a soft gradient through the last stop."""
    # Last stop wins at a coincident position, including 1.0 wrapping to zero.
    stops = {position % 1: colorsys.hsv_to_rgb(*hsv) for position, hsv in swatches}
    ordered = sorted(stops)
    colors = np.array([stops[k] for k in ordered], dtype=np.float32)
    if len(colors) == 1:
        return colors
    points = np.asarray(ordered)
    samples = np.arange(2048)/2048
    left = np.searchsorted(points, samples, side='right') - 1
    width = (points[(left+1) % len(points)] - points[left]) % 1
    f = (((samples-points[left]) % 1)/width)[:, None]
    a, b, c, d = (colors[(left+k) % len(colors)] for k in (-1, 0, 1, 2))
    prev_width = (points[left]-points[(left-1) % len(points)]) % 1
    next_width = (points[(left+2) % len(points)]-points[(left+1) % len(points)]) % 1
    tangent_b = (c-a)*(width/(prev_width+width))[:, None]
    tangent_c = (d-b)*(width/(width+next_width))[:, None]
    values = b + f*(tangent_b + f*(3*(c-b)-2*tangent_b-tangent_c + f*(2*(b-c)+tangent_b+tangent_c)))
    return np.clip(values, 0, 1).astype(np.float32)


def _disc_field(size, center, radius, count, ratio, turn, angle, dx, dy, fx, fy, falloff, diffusion, lens):
    # Build one material coordinate for the visible portion of each disc.
    # The largest disc's gradient continues beyond its rim to fill the canvas.
    w, h = size
    cx, cy = center
    y, x = np.ogrid[:h, :w]
    x = x.astype(np.float32) + .5
    y = y.astype(np.float32) + .5
    field = np.empty((h, w), dtype=np.float32)
    opaque = np.zeros((h, w), dtype=np.uint8)
    rims = []
    focus_distance = math.hypot(fx, fy)**falloff
    lens_x, lens_y = lens
    pad = 1 + diffusion*math.hypot(max(abs(lens_x), abs(w-lens_x)), max(abs(lens_y), abs(h-lens_y)))
    for index in range(count):
        if radius < .45 and index:
            break
        a = math.radians(angle + index * turn)
        c, s = math.cos(a), math.sin(a)
        center_x = cx + radius * (c*dx - s*dy)
        center_y = cy + radius * (s*dx + c*dy)
        x0 = max(0, math.floor(center_x-radius-pad)) if index else 0
        x1 = min(w, math.ceil(center_x+radius+pad)) if index else w
        y0 = max(0, math.floor(center_y-radius-pad)) if index else 0
        y1 = min(h, math.ceil(center_y+radius+pad)) if index else h
        if x0 < x1 and y0 < y1:
            xx, yy = x[:, x0:x1] - center_x, y[y0:y1] - center_y
            dist = np.hypot(xx, yy)
            gradient = np.hypot(xx/radius-(c*fx-s*fy), yy/radius-(s*fx+c*fy))
            if falloff != 1.:
                gradient **= falloff
            gradient -= focus_distance
            region = field[y0:y1, x0:x1]
            if index == 0:
                region[:] = gradient
            else:
                # A radial lens spreads each edge in proportion to its
                # distance and direction from the center of the image.
                projection = xx*(x[:, x0:x1]-lens_x) + yy*(y[y0:y1]-lens_y)
                width = np.maximum(1., diffusion*np.abs(projection)/np.maximum(1., dist))
                alpha = np.clip(.5+(radius-dist)/width, 0, 1)
                alpha *= alpha*(3-2*alpha)
                solid = alpha >= 1
                region[solid] = gradient[solid]
                opaque[y0:y1, x0:x1][solid] = index
                iy, ix = np.nonzero((alpha > 0) & ~solid)
                if len(iy):
                    pixels = (iy+y0)*w + (ix+x0)
                    rims.append((index, pixels, gradient[iy, ix], alpha[iy, ix, None]))
        radius *= ratio
    # Later opaque discs completely cover earlier edge samples. The remaining
    # translucent rims composite in drawing order, including overlapping ones.
    blends = []
    for index, pixels, gradient, alpha in rims:
        visible = opaque.ravel()[pixels] < index
        if np.any(visible):
            blends.append((pixels[visible], gradient[visible], alpha[visible]))
    return field, blends


_cached_field = lru_cache(maxsize=1)(_disc_field)


def render_gradients(p, size, center, unit, seconds):
    w, h = size
    movement = travel(p, seconds)
    moving = any(p[k] for k in ('rotation', 'pan_x', 'pan_y', 'disc_travel_x', 'disc_travel_y'))
    build = _cached_field if not moving and w*h <= 2_100_000 else _disc_field
    field, blends = build(size, center, unit*p['expansion'], int(p['copies']), p['copy_scale'],
                  p['copy_angle'], (p['orientation'] + p['rotation']*seconds) % 360,
                  p['disc_x'] + movement*p['disc_travel_x'],
                  p['disc_y'] + movement*p['disc_travel_y'],
                  p['focus_x'], p['focus_y'], p['falloff'], p['diffusion'],
                  (w*.5 + unit*p['lens_x'], h*.5 + unit*p['lens_y']))
    sign = (1, -1, 0)[int(p['direction'])]
    cycle = (sign * seconds / p['cycle']) % 1
    angle = 2*math.pi*cycle
    ease = 2*math.pi*p['ease_phase']
    clock = cycle + p['pace_swing']*(math.sin(angle+ease)-math.sin(ease))/(2*math.pi)
    ramp = _ramp(tuple((p[key+'_position'], tuple(p[key+'_'+ch] for ch in CHANNELS))
                       for key in STOP_KEYS))
    phase = clock + p['color_phase']

    def sample(distance):
        coordinate = (p['spread']*distance + phase) % 1
        return ramp[(coordinate*len(ramp)).astype(np.int32) % len(ramp)]

    rgb = sample(field)
    flat = rgb.reshape(-1, 3)
    for pixels, gradient, alpha in blends:
        flat[pixels] += alpha*(sample(gradient)-flat[pixels])
    if p['softness']:
        raster = Image.fromarray(np.uint8(np.clip(rgb*255+.5, 0, 255)))
        rgb = np.asarray(raster.filter(ImageFilter.GaussianBlur(p['softness']*unit/720)), dtype=np.float32)/255.
    return rgb*p['light']
