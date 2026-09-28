"""Opt-in recording faults and glass optics, independent of source geometry."""
import numpy as np
from PIL import Image, ImageFilter

from synth_text import color


def noise_field(rng, size, cells, smooth=True):
    grid = rng.random((max(2, cells[1]), max(2, cells[0]))).astype(np.float32)
    return np.asarray(Image.fromarray(grid).resize(size, Image.Resampling.BILINEAR if smooth else Image.Resampling.NEAREST))


def exposure_wash(arr, p, rng):
    h, w = arr.shape[:2]
    y, x = np.mgrid[:h, :w].astype(np.float32)
    x /= w; y /= h
    center = rng.uniform(-.1, 1.1); slope = rng.uniform(-.5, .5)
    envelope = np.exp(-((y - center + slope * (x-.5)) / rng.uniform(.14, .5)) ** 2)
    cloud = noise_field(rng, (w, h), (5, 9))
    hue = p['hue'] + rng.uniform(-1, 1) * p['hue_spread']
    ink = color(hue, .7, 1.)
    light = envelope * (.25 + cloud) * (rng.uniform(.15, 1.25) * p['wash'])
    # Light reaches the lettering as well as the shadows; grain belongs to
    # the exposure, so a bright wash does not leave a smooth digital overlay.
    light *= np.clip(1 + rng.normal(0, .13, (h, w)), 0, 2)
    return arr * (1 - light[..., None] * .35) + light[..., None] * ink


def broken_sync(arr, p, rng):
    """Ragged blanking, line noise and chroma streaks sharing one damaged signal."""
    h, w = arr.shape[:2]
    y, x = np.mgrid[:h, :w].astype(np.float32)
    x /= w; y /= h
    fine = noise_field(rng, (w, h), (max(8, w//3), h), False)
    streak = noise_field(rng, (w, h), (max(6, w//18), max(8, h//2)), False)
    # Broad blanking intervals have uneven/diagonal edges, with fresh short
    # horizontal chips along their boundaries instead of a tiled noise sheet.
    slope = rng.uniform(-.24, .24)
    phase = rng.uniform(0, 1)
    chips = noise_field(rng, (w, h), (23, 45), False)
    carrier = (y + slope*x + (chips-.5)*.075 + phase) % 1
    white = (carrier < rng.uniform(.04, .24)).astype(np.float32)
    snow = ((carrier > .29) & (carrier < rng.uniform(.53, .9))).astype(np.float32)
    static = np.clip((fine*.75 + streak*.75-.25), 0, 1)
    red = noise_field(rng, (w, h), (35, max(10, h//3)), False)
    blue = noise_field(rng, (w, h), (28, max(10, h//3)), False)
    chroma = np.stack((red-.5, .5-red, blue-.5), axis=2)
    damaged = (white[..., None] * (.82 + fine[..., None]*.16)
               + snow[..., None] * np.clip(static[..., None] + chroma * p['static_chroma'], 0, 1))
    surviving = np.clip(1 - white - snow, 0, 1)
    damaged += surviving[..., None] * (arr*.5 + np.maximum(chroma, 0)*.10*p['static_chroma'])
    if p['sync_tear']:
        rows = noise_field(rng, (w, h), (2, 12))[:, 0]
        displacement = (rows-.5) * .18 + .055*np.sin(y[:, 0]*rng.uniform(20, 50) + phase*6.28)
        shift = (displacement[:, None] + (chips-.5)*.015) * w * p['sync_tear']
        ix = np.clip(np.rint(np.arange(w)[None, :] + shift).astype(int), 0, w-1)
        damaged = damaged[np.arange(h)[:, None], ix]
    return damaged


def glass_optics(arr, p, rng, seed):
    h, w = arr.shape[:2]
    out = arr
    if p['halo']:
        luma = np.clip(np.max(arr, axis=2), 0, 1)
        highlights = np.clip((luma - p['halo_threshold']) / (1-p['halo_threshold']), 0, 1)
        light = Image.fromarray((highlights*255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(min(w, h)*p['halo_radius']))
        glow = np.asarray(light, dtype=np.float32) / 255
        glow *= (1 - luma*.8) * np.clip(1 + rng.normal(0, .1, (h, w)), 0, 2)
        out = out + (glow * p['halo'])[..., None] * color(p['halo_hue'], .92, 1.)
    if not p['screen']: return out
    x, y = np.meshgrid((np.arange(w)+.5)/w*2-1, (np.arange(h)+.5)/h*2-1)
    # The glass has a fixed irregular edge; electronic texture remains fresh.
    fixed = np.random.default_rng(np.random.SeedSequence((seed, 712)))
    edge_noise = noise_field(fixed, (w, h), (60, 30))
    inset = p['screen_inset'] * 2
    distance = 1 - inset - (np.abs(x)**8 + np.abs(y)**8)**(1/8)
    distance -= (edge_noise-.5) * .065 * p['screen_wear'] * (.4 + .6*(y+1)/2)
    aperture = np.clip(distance * 70 + .5, 0, 1)
    upper = np.exp(-((y + 1-inset-.012 - .028*x*x)/.008)**2)
    reflection = upper * np.clip(1-x*x, 0, 1) * (.3 + edge_noise) * .18
    surface = noise_field(rng, (w, h), (max(8, w//7), h))
    cloud = noise_field(fixed, (w, h), (12, 16))
    coating = (surface * .028 + cloud * .035) * p['screen_wear']
    coating *= np.clip(1-y*y, 0, 1)
    glass = (out + coating[..., None] * color(p['halo_hue'], .86, 1.)) * aperture[..., None]
    glass += reflection[..., None] * color(p['halo_hue'], .72, 1.)
    return out * (1-p['screen']) + glass * p['screen']
