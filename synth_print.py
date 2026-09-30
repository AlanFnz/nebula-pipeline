"""Seeded paper/ink rendering and a rotating cluster of replaceable stamps.

All state comes from time and a seed, including held scanner registration.
Built-in shapes need no assets; custom silhouettes are embedded in documents.
"""
from __future__ import annotations

from functools import lru_cache
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from synth_artwork import decode_artwork, project_artwork
from synth_ink_timing import gesture_phase


INK_PALETTES = (
    ((.89, .18, .75), (.015, .72, .87), (.99, .94, .37), (.93, .96, .94)),
    ((.94, .31, .12), (.08, .44, .72), (.97, .81, .43), (.96, .93, .82)),
    ((.94, .94, .88), (.64, .66, .60), (.92, .91, .81), (.98, .98, .94)),
)


def _rng(seed, *parts):
    return np.random.default_rng(np.random.SeedSequence([int(seed), *(int(x) & 0xffffffff for x in parts)]))


def _ease(x):
    x = np.clip(x, 0., 1.)
    return x * x * (3 - 2 * x)


def bloom_phase(time, p, speed=1.):
    """One cyclic unfold/hold/refold gesture, with an optional manual spread."""
    clock, phase, opening, closing = gesture_phase(time, p, speed)
    return clock, phase, p['opening'] * ((1 - p['cycle']) + p['cycle'] * opening * closing)


def _rotation(yaw, pitch, roll):
    cy, sy = math.cos(yaw), math.sin(yaw)
    cx, sx = math.cos(pitch), math.sin(pitch)
    cz, sz = math.cos(roll), math.sin(roll)
    return np.array(((cz, -sz, 0), (sz, cz, 0), (0, 0, 1))) @ np.array(((1, 0, 0), (0, cx, -sx), (0, sx, cx))) @ np.array(((cy, 0, sy), (0, 1, 0), (-sy, 0, cy)))


@lru_cache(maxsize=128)
def _outline(seed, identity, points, depth, irregularity):
    rng = _rng(seed, 19, identity)
    step = math.tau / points
    vertices = []
    for i in range(points):
        angle = i * step + rng.uniform(-.15, .15) * step * irregularity
        outer = 1 + rng.uniform(-.28, .2) * irregularity
        inner = (1 - depth) * (1 + rng.uniform(-.18, .18) * irregularity)
        for offset, radius in ((-.5, inner), (-.30, inner * 1.06), (-.16, inner * 1.12), (0., outer), (.22, inner * 1.10)):
            a = angle + offset * step
            vertices.append((math.cos(a) * radius, math.sin(a) * radius, 0.))
    value = np.array(vertices, dtype=np.float32)
    value.setflags(write=False)
    return value


def stamp_outline(p, seed, identity, artwork=None):
    """Local silhouette; the common animation below owns all placement/motion."""
    shape = int(p.get('shape', 0))
    if shape == 0:
        vertices = _outline(seed, identity, int(p['points']), p['point_depth'], p['irregularity']).copy()
    elif shape in (1, 5):
        vertices = np.array(((-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0)), dtype=np.float32)
        if artwork is not None:
            vertices[:, 0] *= artwork.width / max(artwork.size)
            vertices[:, 1] *= artwork.height / max(artwork.size)
    else:
        sides = 128 if shape == 2 else 3 if shape == 3 else int(p['sides'])
        angles = np.arange(sides) * math.tau / sides - math.pi / 2
        vertices = np.column_stack((np.cos(angles), np.sin(angles), np.zeros(sides))).astype(np.float32)
    vertices[:, 0] *= p.get('shape_width', 1.)
    vertices[:, 1] *= p.get('shape_height', 1.)
    if p.get('shape_rotation', 0):
        vertices = vertices @ _rotation(0, 0, math.radians(p['shape_rotation'])).T
    return vertices


def render_ink_bloom(arr, p, time, speed, seed, content_size=None, offset=(0., 0.)):
    if p['opacity'] == 0:
        return arr
    h, w = arr.shape[:2]
    artwork = None
    if p.get('shape', 0) == 5:
        if not p.get('artwork'): return arr
        artwork = decode_artwork(p['artwork'])
    clock, phase, opening = bloom_phase(time, p, speed)
    # Smooth turning passes through two edge-on views while the stamps unfold.
    yaw_progress = float(np.interp(phase, (0, .15, .30, .42, .56, .68, .78, 1), (0, .05, .25, .5, .60, .75, 1, 1)))
    yaw = math.radians(p['turn']) + yaw_progress * math.tau * p['revolutions']
    roll = math.radians(p['rotation'] + p['tumble'] * 140 * math.sin(math.tau * (phase - .30)))
    pitch = math.radians(p['tilt'] * math.sin(math.tau * phase))
    matrix = _rotation(yaw, pitch, roll)
    cw, ch = content_size or (w, h)
    canvas_scale = min(cw, ch)
    radius = p['size'] * canvas_scale * (.94 + .06 * opening)
    spread = p['spread'] * canvas_scale * opening
    count = int(p['count'])
    rng = _rng(seed, 31)
    local_offsets = rng.uniform(-1, 1, (count, 3))
    palette = np.array(INK_PALETTES[int(p['palette'])], dtype=np.float32)
    gray = palette.mean(axis=1, keepdims=True)
    palette = gray + (palette - gray) * p['saturation']
    # Center magenta, then alternating cyan/white/yellow impressions.
    inks = (0, 2, 3, 1, 1, 0, 1, 2, 3, 0, 1, 2, 3)
    cards = []
    for i in range(count):
        a = math.tau * (i - 1) / max(1, count - 1) - .2
        center = np.array((math.cos(a) * spread, math.sin(a) * spread, 0.)) if i else np.array((0., 0., radius * .18))
        if i:
            center[2] += spread * p['cluster_depth'] * (-1 if i % 2 else 1)
        center += local_offsets[i] * spread * p['disorder'] * .10
        # A thin stack is visible before opening; this is geometric, not a fade.
        center[2] += (count - i) * radius * p['stack_spacing'] * (1 - opening)
        center = center @ matrix.T
        vertices = stamp_outline(p, seed, i, artwork)
        vertices *= radius * (1 + local_offsets[i, 0] * p['disorder'] * .16) * ((.88 + .12 * opening) if i else 1.03)
        fan = math.radians(p['fan'] * local_offsets[i, 1]) if i else 0.
        fold = math.pi / 2 * math.sin(yaw) ** 2 * p['center_fold'] if i == 0 else fan * .45
        vertices = vertices @ _rotation(fan, fold, local_offsets[i, 2] * .18).T
        vertices = vertices @ matrix.T + center
        # Gentle orthographic depth keeps the print-like silhouettes readable.
        perspective = 1 / np.maximum(.4, 1 - vertices[:, 2] / canvas_scale * p['perspective'])
        xy = vertices[:, :2] * perspective[:, None]
        xy[:, 0] += w * (.5 + p['position_x'] * .5) if content_size is None else w / 2 + cw * p['position_x'] * .5
        xy[:, 1] += h * (.5 + p['position_y'] * .5) if content_size is None else h / 2 + ch * p['position_y'] * .5
        if offset[0]: xy[:, 0] += offset[0]
        if offset[1]: xy[:, 1] += offset[1]
        cards.append((center[2], i, xy))
    result = arr.copy()
    yy, xx = np.mgrid[:h, :w].astype(np.float32)
    for _z, i, xy in sorted(cards, key=lambda card: card[0]):
        if artwork is None:
            mask = Image.new('L', (w, h)); ImageDraw.Draw(mask).polygon([tuple(point) for point in xy], fill=255)
        else:
            mask = project_artwork(artwork, xy, (w, h))
        coverage = np.asarray(mask, dtype=np.float32) / 255 * p['opacity']
        first = palette[inks[i]]
        second = palette[0 if inks[i] in (2, 3) else 2 if inks[i] == 1 else 1]
        reverse = float(_ease((math.cos(yaw) + .5) / .5)) * p['back_ink']
        first = first * (1 - reverse) + palette[0] * reverse
        second = second * (1 - reverse * .75) + palette[0] * reverse * .75
        # Slightly offset ink impressions give the colored seams in each stamp.
        local_x = (xx - xy[:, 0].mean()) / max(1, radius)
        local_y = (yy - xy[:, 1].mean()) / max(1, radius)
        seam = np.clip((local_x * math.cos(i * 1.8) + local_y * math.sin(i * 1.8) - .05) * 2, 0, 1) * p['split_ink'] * (1 if i else .2)
        color = first[None, None, :] * (1 - seam[..., None]) + second[None, None, :] * seam[..., None]
        result = result * (1 - coverage[..., None]) + color * coverage[..., None]
    return result


@lru_cache(maxsize=12)
def _paper_noise(seed, width, height, grain_size, layer):
    rng = _rng(seed, 71, layer)
    shape = (max(2, round(height / grain_size * (1.3 if layer == 2 else 1))), max(2, round(width / grain_size / (1.3 if layer == 2 else 1))))
    values = rng.random(shape).astype(np.float32)
    image = Image.fromarray(values)
    resample = Image.Resampling.BILINEAR if layer else Image.Resampling.BICUBIC
    result = np.asarray(image.resize((width, height), resample), dtype=np.float32)
    if layer == 2:
        y, x = np.mgrid[:height, :width]
        result = result[y, (x + y // 2) % width]
    result.setflags(write=False)
    return result


def _fresh_noise(rng, width, height, cell_x, cell_y):
    """One full-frame random field, without texture reuse or wrapped edges."""
    shape = (max(2, math.ceil(height / cell_y)), max(2, math.ceil(width / cell_x)))
    values = rng.standard_normal(shape).astype(np.float32)
    field = np.asarray(Image.fromarray(values).resize((width, height), Image.Resampling.BILINEAR), dtype=np.float32)
    return (field - field.mean()) / max(float(field.std()), 1e-6)


def frame_noise_background(width, height, p, tick, seed):
    """Independent grain and density patches for every held frame/seed."""
    rng = _rng(seed, 109, tick)
    scale = min(width, height) / 720
    size = max(.7, p['noise_size'] * scale)
    fine = _fresh_noise(rng, width, height, size, size)
    flecks = _fresh_noise(rng, width, height, size * 1.8, max(.7, size * .8))
    coarse = _fresh_noise(rng, width, height, max(6, min(width, height) * .11), max(6, min(width, height) * .14))
    density = (1 - p['noise_clumps']) + p['noise_clumps'] * np.clip(.5 + coarse * .4, .05, 1.5)
    pores = np.maximum(flecks - 1.2, 0) ** 1.3
    noise = fine * .007 + pores * .10 * density + coarse * p['noise_clumps'] * .003
    dust = (rng.random((height, width)) > 1 - p['dust'] * .0004) * rng.uniform(.15, .4, (height, width))
    return np.maximum(0., p['noise_floor'] + (noise + dust) * p['noise_amount']).astype(np.float32)


def _background_mask(coverage, radius):
    # Protect the source and the full support of its optical blur. Feather only
    # outside that guard, so switching backgrounds cannot repaint the figures.
    ink = Image.fromarray(np.uint8(coverage > .5) * 255)
    guard = ink.filter(ImageFilter.MaxFilter(2 * max(1, math.ceil(radius * 3 + 1)) + 1))
    hard = np.asarray(guard, dtype=np.float32) / 255
    soft = np.asarray(guard.filter(ImageFilter.GaussianBlur(max(1., radius * 2))), dtype=np.float32) / 255
    return 1 - np.maximum(hard, soft)


def render_print_surface(arr, p, time, speed, seed):
    if p['mix'] == 0:
        return arr
    h, w = arr.shape[:2]
    scale = min(w, h) / 720
    tick = math.floor(time * speed * p['cadence'] + 1e-8)
    rng = _rng(seed, 47, tick)
    # The sheet moves a little between scans; the fibers themselves persist.
    fine = _paper_noise(seed, w, h, max(.7, p['grain_size'] * scale), 0)
    coarse = _paper_noise(seed, w, h, max(2., p['grain_size'] * scale * 100), 1)
    fibers = _paper_noise(seed, w, h, max(1., p['grain_size'] * scale * 1.5), 2)
    sx, sy = np.rint(rng.uniform(-1, 1, 2) * p['paper_motion'] * min(w, h)).astype(int)
    fine = np.roll(fine, (sy, sx), (0, 1)); coarse = np.roll(coarse, (sy, sx), (0, 1))
    fibers = np.roll(fibers, (sy, sx), (0, 1))
    live = rng.random((h, w)).astype(np.float32)
    grain = fine * (1 - p['boil']) + live * p['boil']
    y, x = np.mgrid[:h, :w].astype(np.float32)
    registration = rng.uniform(-1, 1, 3)
    angle = registration[2] * p['rotation_jitter'] * math.pi / 180
    cx, cy = x - w / 2, y - h / 2
    # Clamp samples: registration never creates a blank edge or wraps the image.
    src_x = np.rint(cx * math.cos(angle) + cy * math.sin(angle) + w / 2 + registration[0] * p['registration'] * min(w, h))
    src_y = np.rint(-cx * math.sin(angle) + cy * math.cos(angle) + h / 2 + registration[1] * p['registration'] * min(w, h))
    edge = ((grain - .5) * 20 + (fibers - .5) * 14) * p['edge_wear'] * scale
    src_x = np.clip((src_x + edge).astype(int), 0, w - 1); src_y = np.clip((src_y - edge * .7).astype(int), 0, h - 1)
    signal = np.maximum(arr[src_y, src_x] - np.array((.055, .067, .055), dtype=np.float32), 0.)
    coverage = np.clip(signal.max(axis=2) * 6, 0, 1)
    tooth = np.clip((grain - .23) * 2.1, 0, 1)
    signal *= (1 - p['ink_wear'] * (1 - tooth))[..., None]
    signal *= (1 + (grain - .5) * p['ink_grain'] * 1.3)[..., None]
    # Neutral charcoal stock with sparse pale fibers and broad mottled patches.
    patches = np.clip((coarse - .47) * 6, 0, 1)
    paper = p['black_level'] + p['paper_grain'] * (fine - .5) * .016
    paper += p['fibers'] * np.maximum(fibers - .50, 0) ** 1.5 * patches * .85
    paper += (coarse - .5) * p['mottle'] * .035
    paper += (live - .5) * p['boil'] * p['paper_grain'] * .020
    result = np.maximum(paper, 0)[..., None] + signal
    dust = (live > 1 - p['dust'] * .003) * rng.uniform(.12, .4, (h, w))
    result += dust[..., None] * (1 - coverage[..., None] * .7)
    if p['softness']:
        image = Image.fromarray(np.clip(result * 255, 0, 255).astype(np.uint8))
        result = np.asarray(image.filter(ImageFilter.GaussianBlur(p['softness'] * scale)), dtype=np.float32) / 255
    # Fine scan noise follows the optical softness, retaining grit at export size.
    result += (live - .5)[..., None] * p['ink_grain'] * .25 * np.sqrt(np.clip(signal.mean(axis=2), 0, 1))[..., None]
    if p.get('background_mode', 0) == 1:
        background = frame_noise_background(w, h, p, tick, seed)
        background_mix = _background_mask(coverage, p['softness'] * scale)[..., None]
        result = result * (1 - background_mix) + background[..., None] * background_mix
    return arr * (1 - p['mix']) + result * p['mix']
