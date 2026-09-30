"""Source-independent stretched contours and eroded luminous image treatments."""
import colorsys
import math

import numpy as np
from PIL import Image, ImageFilter


def held_clock(time, speed, cadence):
    clock = time * speed
    return math.floor(clock * cadence + 1e-8) / cadence if cadence else clock


def echo_scale(p, time, speed):
    phase = (held_clock(time, speed, p['cadence']) / p['period'] + p['phase']) % 1
    if p['motion'] == 1:
        amount = 1 - (1-phase) ** p['ease']
    elif p['motion'] == 2:
        amount = (.5 - .5 * math.cos(phase * math.tau)) ** (1 / p['ease'])
    else:
        amount = 1.
    return p['minimum'] + (p['stretch_y'] - p['minimum']) * amount


def render_stretch_echo(arr, p, time, speed, origin, reference_size, echo_source=None):
    if not p['mix'] or (not p['opacity'] and p['source'] == 1): return arr
    h, w = arr.shape[:2]
    unit = min(reference_size) / 720
    cx = origin[0] + p['position_x'] * reference_size[0]
    cy = origin[1] + p['position_y'] * reference_size[1]
    sy = echo_scale(p, time, speed)
    # Extract highlights, not a text mask: footage and other objects use the
    # same effect. The threshold keeps a dark backdrop out of the contour.
    highlights = arr if echo_source is None else echo_source
    light = np.clip((highlights.max(axis=2) - p['threshold']) / max(.01, 1-p['threshold']), 0, 1)
    source = Image.fromarray((light * 255).astype(np.uint8))
    echo = np.zeros((h, w), dtype=np.float32)
    for index in range(p['copies']):
        fraction = (index + 1) / p['copies']
        scale_x = 1 + (p['stretch_x'] - 1) * fraction
        scale_y = 1 + (sy - 1) * fraction
        stretched = source.transform((w, h), Image.Transform.AFFINE,
            (1/scale_x, 0, cx-cx/scale_x, 0, 1/scale_y, cy-cy/scale_y), Image.Resampling.BICUBIC)
        solid = np.asarray(stretched, dtype=np.float32) / 255
        outline = solid
        if p['outline']:
            radius = max(1, min(15, round(p['stroke'] * unit)))
            edge = (np.asarray(stretched.filter(ImageFilter.MaxFilter(2*radius+1)), dtype=np.float32)
                    - np.asarray(stretched.filter(ImageFilter.MinFilter(2*radius+1)), dtype=np.float32)) / 255
            outline = edge * p['outline'] + solid * (1-p['outline'])
        echo = np.maximum(echo, outline * (.55 + .45 * fraction))
    # Screen the echo behind the intact source so the center stays readable.
    ink = np.array(colorsys.hsv_to_rgb(p['hue'], p['saturation'], 1.), dtype=np.float32)
    out = np.maximum(arr * p['source'], echo[..., None] * ink * p['opacity'])
    return arr * (1-p['mix']) + out * p['mix']


def _field(rng, size, cell_x, cell_y):
    w, h = size
    grid = rng.random((max(2, math.ceil(h / max(.5, cell_y))), max(2, math.ceil(w / max(.5, cell_x))))).astype(np.float32)
    return np.asarray(Image.fromarray(grid).resize(size, Image.Resampling.BILINEAR))


def _blur(field, radius_x, radius_y):
    # Work on float pixels until the blur boundary; bounded 8-bit blur is
    # deterministic and uses Pillow rather than adding a runtime dependency.
    h, w = field.shape
    image = Image.fromarray((np.clip(field, 0, 1)*255).astype(np.uint8))
    # Compress the axis with the wider kernel. Never enlarge an intermediate
    # image: extreme anisotropy should not allocate many full-size canvases.
    if radius_y >= radius_x:
        reduced = (w, max(1, round(h * radius_x / radius_y)))
    else:
        reduced = (max(1, round(w * radius_y / radius_x)), h)
    compressed = image.resize(reduced, Image.Resampling.BILINEAR)
    blurred = compressed.filter(ImageFilter.GaussianBlur(max(.01, min(radius_x, radius_y))))
    return np.asarray(blurred.resize((w, h), Image.Resampling.BILINEAR), dtype=np.float32) / 255


def render_signal_etch(arr, p, time, speed, seed, reference_size, pulse_source=None):
    if not p['mix']: return arr
    h, w = arr.shape[:2]; unit = min(reference_size) / 720
    clock = time * speed
    frame = math.floor(clock * p['cadence'] + 1e-8) if p['cadence'] else 0
    rng = np.random.default_rng(np.random.SeedSequence((seed, frame, 815)))
    cell = max(.5, p['grain_size'] * unit)
    streak = _field(rng, (w, h), cell * p['streak'], cell)
    fine = _field(rng, (w, h), cell, cell)
    y, x = np.mgrid[:h, :w]
    rows = _field(rng, (w, h), max(1, w/8), cell) - .5
    shift = np.rint(rows * p['roughness'] * unit).astype(int)
    ix = x + shift
    warped = arr[y, np.clip(ix, 0, w-1)].copy()
    warped[(ix < 0) | (ix >= w)] = 0
    light = warped.max(axis=2)
    support = _blur(light, max(.5, p['spread_x'] * unit), max(.5, p['spread_y'] * unit))
    phase = (clock / p['period'] + p['phase']) % 1
    pulse = math.exp(-((phase * p['period']) / max(.01, p['pulse_seconds'])) ** 2)
    fog = np.maximum(0., (streak-.34) * 2.6 + (fine-.5) * .3)
    # Noise only catches light already in the input. Empty black stays black.
    scatter = support * fog * p['scatter']
    # A preceding echo can change height during the flash. Derive the pulse
    # from the un-stretched source so the plume keeps a stable spatial extent.
    pulse_light = light if pulse_source is None else pulse_source.max(axis=2)
    if pulse * p['pulse'] > .001 and pulse_light.any():
        mass = pulse_light.sum(axis=0)
        center = float(mass @ np.arange(w) / mass.sum())
        variance = float(mass @ (np.arange(w)-center)**2 / mass.sum())
        focus = np.exp(-.5 * (np.arange(w)-center)**2 / max(1., variance * .22))
        rows_mass = pulse_light.sum(axis=1)
        cy = float(rows_mass @ np.arange(h) / rows_mass.sum())
        flare_source = Image.fromarray(pulse_light).transform((w,h), Image.Transform.AFFINE,
            (1, 0, 0, 0, 1/p['pulse_stretch'], cy-cy/p['pulse_stretch']), Image.Resampling.BILINEAR)
        flare = _blur(np.asarray(flare_source), max(.5, p['spread_x']*unit), max(.5, p['pulse_spread']*unit))
        scatter += flare * fog * pulse * p['pulse'] * (1-p['pulse_focus']+p['pulse_focus']*focus)
    worn = warped * np.clip(1 + (streak-.55) * p['grain'] * 2.8, 0, 2.5)[..., None]
    worn *= (1 - p['erosion'] * np.clip(1-(streak-.38)*5., 0, 1))[..., None]
    if p['core']:
        radius = max(1, round(4 * unit))
        interior = Image.fromarray((np.clip(light,0,1)*255).astype(np.uint8)).filter(ImageFilter.MinFilter(2*radius+1))
        retention = np.asarray(interior, dtype=np.float32) / 255 * p['core']
        worn = worn * (1-retention[...,None]) + warped * retention[...,None]
    out = worn + scatter[..., None]
    return arr * (1-p['mix']) + out * p['mix']
