"""Image-keyed scan modulation and the optical texture of a filmed CRT.

Both operations accept ordinary RGB pixels. No portrait detection, baked media
or temporal buffer is involved; a seek reconstructs the same oscillator state.
Distances use a 720-pixel reference edge, independent of delivery resolution.
"""
import colorsys
import math

import numpy as np
from PIL import Image, ImageFilter


def _smooth(low, high, value):
    a = np.clip((value-low)/max(.0001, high-low), 0., 1.)
    return a*a*(3-2*a)


def _blur(arr, radius):
    if radius <= 0: return arr
    return np.asarray(Image.fromarray(np.uint8(np.clip(arr*255, 0, 255))).filter(
        ImageFilter.GaussianBlur(radius)), dtype=np.float32)/255


def _noise(x, y, seed):
    # Integer spatial hashing keeps layouts identical at different resolutions.
    with np.errstate(over='ignore'):
        v = np.asarray(x, dtype=np.int64).astype(np.uint32)*np.uint32(374761393)
        v = v+np.asarray(y, dtype=np.int64).astype(np.uint32)*np.uint32(668265263)+np.uint32(seed & 0xffffffff)
        v = (v ^ (v >> 13))*np.uint32(1274126177)
        v ^= v >> 16
    return v.astype(np.float32)/4294967296.


def _field(x, y, seed):
    ix, iy = np.floor(x), np.floor(y)
    fx, fy = x-ix, y-iy
    fx, fy = fx*fx*(3-2*fx), fy*fy*(3-2*fy)
    a = _noise(ix, iy, seed)*(1-fx)+_noise(ix+1, iy, seed)*fx
    b = _noise(ix, iy+1, seed)*(1-fx)+_noise(ix+1, iy+1, seed)*fx
    return a*(1-fy)+b*fy


def _row_sample(arr, displacement):
    """Subpixel row displacement with transparent/black edges, never wrapping."""
    h, w = arr.shape[:2]
    sx = np.arange(w, dtype=np.float32)[None, :] - displacement[:, None]
    left = np.floor(sx).astype(np.int32)
    part = sx-left.astype(np.float32)
    row = np.arange(h)[:, None]
    a = arr[row, np.clip(left, 0, w-1)]
    b = arr[row, np.clip(left+1, 0, w-1)]
    if arr.ndim == 3: part = part[..., None]
    out = a*(1-part)+b*part
    valid = (sx >= 0) & (sx <= w-1)
    return out * (valid[..., None] if arr.ndim == 3 else valid)


def signal_region(source, p, reference_size):
    """Soft hue/luma selection, optionally faded along a canvas direction."""
    source = np.clip(source, 0., 1.)
    luma = source @ np.array((.2126, .7152, .0722), dtype=np.float32)
    mode = int(p['region'])
    mask = np.ones_like(luma)
    if mode:
        mask *= _smooth(p['key_floor'], p['key_floor']+p['key_softness'], luma)
    if mode == 2:
        high, low = source.max(axis=2), source.min(axis=2)
        delta = np.maximum(high-low, 1e-6)
        r, g, b = source.transpose(2, 0, 1)
        hue = np.where(high == r, (g-b)/delta,
                       np.where(high == g, (b-r)/delta+2, (r-g)/delta+4))/6 % 1.
        distance = np.abs((hue-p['key_hue']+.5) % 1.-.5)
        mask *= 1-_smooth(p['key_width'], p['key_width']+p['key_softness']*.3, distance)
        saturation = (high-low)/np.maximum(high, 1e-6)
        mask *= _smooth(p['key_saturation'], p['key_saturation']+.1, saturation)
    if p['key_invert']: mask = 1-mask
    if p['fade']:
        h, w = luma.shape
        unit = min(reference_size)/720
        y, x = np.mgrid[:h, :w].astype(np.float32)
        angle = math.radians(p['fade_angle'])
        distance = ((x-w/2)*math.sin(angle)+(y-h/2)*math.cos(angle))/(720*unit)+.5
        mask *= 1-p['fade']*_smooth(p['fade_start'], p['fade_start']+p['fade_width'], distance)
    return mask.astype(np.float32), luma


def render_scan_modulation(arr, p, time, speed, seed, reference_size, original=None):
    if not p['mix']: return arr
    source = original if p['input'] and original is not None else arr
    mask, luma = signal_region(source, p, reference_size)
    if p['show_key']:
        return np.repeat(mask[..., None], 3, axis=2)
    h, w = mask.shape
    unit = min(reference_size)/720
    clock = time*speed*p['rate']
    if p['cadence']: clock = math.floor(clock*p['cadence']+1e-8)/p['cadence']
    tick = math.floor(clock*17+1e-8)
    yy = (np.arange(h, dtype=np.float32)+.5)/unit
    xx = (np.arange(w, dtype=np.float32)+.5)/unit
    row_position = yy/p['row_pitch']
    row_position += p['irregularity']*2*np.sin(yy*.051+np.sin(yy*.023))
    row = np.floor(row_position).astype(np.int32)
    random = _noise(row, tick, seed)
    coarse = _noise(np.floor(yy/29), math.floor(clock*3), seed+719)
    # Related oscillators move the fine rows and the larger sync disturbances.
    carrier = np.sin(yy*.031+clock*1.7+np.sin(yy*.007-clock*1.3)*2)
    surge = .4+.6*(.5+.5*math.sin(clock*2.7+math.sin(clock*.73)))**3
    shifts = (carrier*p['wave'] + (random-.5)*2*p['tear']
              + (coarse-.5)*p['tear']*.8)*unit*surge
    tone = np.clip((luma-p['black'])/max(.01, p['white']-p['black']), 0, 1)
    # Relief remains sourced from the picture; the modulation cuts into it.
    tone = tone**.72
    keyed = np.stack((mask, mask*tone), axis=2)
    displaced = _row_sample(keyed, shifts)
    alpha, energy = displaced[..., 0], displaced[..., 1]
    if p['streak']:
        for distance, strength in ((1., .28), (-.55, .19), (.32, .23)):
            trail = _row_sample(keyed, shifts+distance*p['streak']*unit)
            alpha = np.maximum(alpha, trail[..., 0]*strength)
            energy = np.maximum(energy, trail[..., 1]*strength)
    carrier_rows = (.5+.5*np.sin(row_position*math.tau+.4))
    gaps = 1-p['depth']*(.35+.65*carrier_rows)
    gaps *= 1-p['irregularity']*.65*(.5+.5*np.sin(yy*.27+clock*2.2))
    gaps *= 1-p['dropout']*(random > .65)
    base = np.array(colorsys.hsv_to_rgb(p['hue'], p['saturation'], 1.), dtype=np.float32)
    signal = energy[..., None]*gaps[:, None, None]*base
    # Short color-lock failures follow scan rows, clipped to displaced signal.
    if p['color_faults']:
        cell = np.floor((xx[None, :]+shifts[:, None]/unit)/p['fragment_width'])
        fault = _noise(cell, row[:, None], seed+tick*137)
        fault_mask = _smooth(1-p['color_faults']*.3, 1-p['color_faults']*.3+.06, fault)
        phase = _noise(cell, row[:, None], seed+tick*137+427)*math.tau
        colors = .5+.5*np.cos(phase[..., None]+np.array((0., 2.1, 4.2), dtype=np.float32))
        signal = signal*(1-fault_mask[..., None]) + energy[..., None]*colors*fault_mask[..., None]
    if p['sparks']:
        pitch = p['spark_size']*3
        sx, sy = xx[None, :]/pitch, yy[:, None]/pitch
        spots = _noise(np.floor(sx), np.floor(sy), seed+tick*331+8)
        dots = np.clip((.23-np.abs((sx+.5) % 1-.5))*7, 0, 1)*np.clip((.25-np.abs((sy+.5) % 1-.5))*7, 0, 1)
        highlights = _smooth(p['spark_threshold'], p['spark_threshold']+.2,
                             _row_sample(luma, shifts))
        if p['spark_fade']:
            highlights *= (1-p['spark_fade']*_smooth(p['spark_end'], p['spark_end']+.2,
                                                    np.arange(h, dtype=np.float32)/h))[:, None]
        signal += (dots*(spots > 1-p['sparks'])*alpha*highlights)[..., None]*p['spark_gain']
    signal *= 2**p['exposure']
    out = arr*(1-alpha[..., None]) + signal
    return (arr*(1-p['mix'])+out*p['mix']).astype(np.float32)


def render_crt_capture(arr, p, time, speed, seed, reference_size):
    if not p['mix']: return arr
    h, w = arr.shape[:2]
    unit = min(reference_size)/720
    clock = time*speed*p['rate']
    if p['cadence']: clock = math.floor(clock*p['cadence']+1e-8)/p['cadence']
    tick = math.floor(clock*25+1e-8)
    y, x = np.mgrid[:h, :w].astype(np.float32)
    x = (x+.5-w/2)/unit
    y = (y+.5-h/2)/unit
    yy = y[:, 0]
    shifts = p['bend']*unit*(np.sin(yy*.011+clock*.7)+.22*np.sin(yy*.089-clock*2.4))
    signal = _row_sample(arr, shifts)
    # Slow camera/screen beat stays visible even when fine phosphors are below
    # preview Nyquist. It is authored interference, never resize aliasing.
    theta = math.radians(p['angle'])
    u = x*math.cos(theta)+y*math.sin(theta)
    u += p['curvature']*(y/720)**2*90 + p['bend']*np.sin(y*.016+clock*.7)
    uneven = _field(x/100+clock*.013, y/90, seed+592)
    moire_u = u+p['weave']*(uneven-.5)*p['moire_pitch']*3
    ripple = math.tau*(moire_u/p['moire_pitch']+p['drift']*clock*.1)
    ripple += p['curvature']*np.sin(y*.003-clock*.2)
    beat = .5+.5*np.sin(ripple+np.sin(ripple*.19+y*.004)*.7)
    gain = 1-p['moire']*(.3+.7*beat)
    gain *= 1-p['field']*(.25+.75*uneven)
    pitch = p['pitch']*unit
    visibility = float(np.clip((pitch-1.1)/1.4, 0, 1))
    columns = .5+.5*np.sin(math.tau*u/p['pitch'])*visibility
    gain *= 1-p['phosphor']*columns
    exposure = 2**(p['exposure']+p['flicker']*math.sin(clock*9.3)*.18)
    signal *= gain[..., None]*exposure
    pulse = (.5+.5*math.sin(clock*2.1+math.sin(clock*.83)))**14
    blur = (p['softness']+p['focus_drift']*pulse)*unit
    signal = _blur(signal, blur)
    if p['halation']:
        light = np.maximum(signal-p['threshold'], 0)
        signal += _blur(light, p['radius']*unit)*p['halation']
    # Camera grain follows optics, driven by emitted light so black stays black.
    if p['grain']:
        random = _noise(np.floor(x+10000), np.floor(y+10000), seed+tick*1217)
        signal += (random-.5)[..., None]*p['grain']*np.sqrt(np.maximum(signal, 0))
    return (arr*(1-p['mix'])+signal*p['mix']).astype(np.float32)
