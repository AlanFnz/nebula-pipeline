"""Source-independent luminous contours and moving exposure inside a silhouette."""
import math
import numpy as np
from PIL import Image, ImageFilter


def modules(Module, P):
    return (Module('contour_melt', 'Contour melt', 'Soft luminous rims with drifting solid-to-hollow exposure. Works on lettering, shapes and footage.', (
        P('fill', 'Solid fill', .65, 0, 1, .01, 'Interior light. Zero leaves only the contours.'),
        P('hollow', 'Hollow breathing', .8, 0, 1, .01, 'Move between the solid fill and hollow contours. Zero freezes the fill.'),
        P('period', 'Breathing cycle', 2.4, .1, 20, .05),
        P('phase', 'Breathing phase', 0., 0, 1, .01),
        P('width', 'Contour width', 2., .25, 12, .25, 'Pixels at a 720-pixel reference edge.'),
        P('separation', 'Double contour spacing', 5., 0, 24, .25, 'Distance between the luminous rims.'),
        P('drift', 'Exposure drift', .6, 0, 1, .01, 'Traveling uneven exposure across the inside of the shape.'),
        P('softness', 'Edge softness', .8, 0, 4, .1),
        P('glow', 'Contour glow', .35, 0, 2, .01),
        P('grain', 'Emulsion grain', .18, 0, .6, .01, 'Fresh monochrome grain in the luminous parts, leaving black untouched.'),
        P('mix', 'Mix', 1., 0, 1, .01),
    )),)


def render_contour_melt(arr, p, time, speed, seed, reference):
    if not p['mix']: return arr
    h, w = arr.shape[:2]
    scale = min(reference) / 720.
    lum = np.clip(arr.max(axis=2), 0, 1)
    image = Image.fromarray((lum * 255).astype(np.uint8))
    radius = max(.4, (p['width'] + p['separation']) * scale)
    field = np.asarray(image.filter(ImageFilter.GaussianBlur(radius)), dtype=np.float32) / 255.
    band = max(.025, .19 * p['width'] / max(.25, p['width'] + p['separation']))
    outer = np.exp(-((field - .23) / band) ** 2)
    inner = np.exp(-((field - .77) / band) ** 2) if p['separation'] else 0.
    clock = time * speed
    yy, xx = np.mgrid[:h, :w].astype(np.float32)
    phase = clock / p['period'] + p['phase']
    breath = .5 + .5 * math.cos(phase * math.tau)
    moving_fill = .5 + .5 * np.sin(xx / max(1, reference[0]) * 7 - yy / max(1, reference[1]) * 4 + phase * math.tau)
    fill = p['fill'] * ((1 - p['hollow']) + p['hollow'] * ((1 - p['drift']) * breath + p['drift'] * moving_fill))
    signal = np.maximum(outer * .8, inner * .85) + lum * fill
    if p['softness']:
        signal = np.asarray(Image.fromarray(np.uint8(np.clip(signal, 0, 1) * 255)).filter(
            ImageFilter.GaussianBlur(p['softness'] * scale)), dtype=np.float32) / 255
    halo = np.asarray(Image.fromarray(np.uint8(np.clip(signal, 0, 1) * 255)).filter(
        ImageFilter.GaussianBlur(max(.1, 4 * scale))), dtype=np.float32) / 255
    signal = signal + halo * p['glow']
    rng = np.random.default_rng((seed + max(0, math.floor(clock * 25)) * 7919) % 2**32)
    signal *= 1 + rng.normal(0, p['grain'], (h, w)).astype(np.float32)
    # Neutral edges preserve source colors instead of introducing a palette.
    rgb = np.divide(arr, lum[..., None], out=np.ones_like(arr), where=lum[..., None] > .01)
    result = signal[..., None] * rgb
    return arr * (1 - p['mix']) + result * p['mix']
