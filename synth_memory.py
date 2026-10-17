"""A moving luminous form deposits a bounded, deterministic image history.

Past poses are sampled analytically, not from previously rendered frames. Every
seek therefore reconstructs the same memory. Samples use continuous age offsets
and smooth birth/death weights; preview FPS does not change their spacing.
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageFilter

from synth_canvas import content_size, object_offset

MAX_TRACES = 96


def modules(Module, P):
    return (Module('image_memory', 'Image memory',
        'A moving form leaves colored traces of its past positions. Persistence holds the traces, Drift carries them away, and Dissolution erodes older silhouettes. This source generates its own object and history.', (
        P('persistence', 'Persistence', 9., 0, 12, .1, 'Seconds of remembered motion at global speed 1. Zero leaves only the current object.'),
        P('drift', 'Drift', .13, 0, 1, .01, 'How far old traces move after being deposited. Zero keeps their original positions.'),
        P('dissolve', 'Dissolution', .55, 0, 1, .01, 'Older traces soften and break apart. Zero preserves their contours until they fade.'),
        P('trail_opacity', 'Trace strength', .66, 0, 1, .01),
        P('drift_angle', 'Drift direction', -75., -180, 180, 1, '0 moves traces right; 90 moves them down.'),
        P('expansion', 'Trace expansion', .55, -.5, 1, .01, 'Older traces grow or shrink independently of their drift.'),
        P('shape', 'Object shape', 1, 0, 2, 1, choices=('Sphere', 'Ring', 'Polygon')),
        P('size', 'Object size', .12, .04, .6, .01, 'Radius as a fraction of the shorter artwork edge.'),
        P('sides', 'Polygon sides', 5, 3, 12, 1),
        P('rotation', 'Starting rotation', 0., -180, 180, 1),
        P('spin', 'Rotation speed', 12., -120, 120, 1),
        P('path', 'Motion path', 2, 0, 2, 1, choices=('Orbit', 'Figure eight', 'Wandering loops')),
        P('travel', 'Travel distance', .58, 0, 1, .01, 'Overall extent of the path before horizontal and vertical amplitude. Zero holds the object at the center.'),
        P('amplitude_x', 'Horizontal amplitude', 100., 0, 200, 1, 'Left/right motion relative to Travel distance. 0 stops this axis, 100% keeps the original path, 200% doubles its reach. Changes positions, not object width; trace Drift is separate.'),
        P('amplitude_y', 'Vertical amplitude', 100., 0, 200, 1, 'Up/down motion relative to Travel distance. 0 stops this axis, 100% keeps the original path, 200% doubles its reach. Changes positions, not object height; trace Drift is separate.'),
        P('period', 'Motion period', 6.4, 2, 30, .1, 'Seconds per main turn at global speed 1. Wandering loops evolve over several turns.'),
        P('variation', 'Motion variation', .65, 0, 1, .01, 'Smooth changes of speed and curvature. No sudden position jumps.'),
        P('phase', 'Starting phase', .12, 0, 1, .01),
        P('palette', 'Palette', 0, 0, 3, 1, choices=('Amber / lagoon', 'Rose / ultraviolet', 'Silver / phosphor', 'Ember / ink')),
        P('color_speed', 'Color evolution', .10, 0, .5, .01, 'Color cycles per source second. Zero keeps the deposition color fixed; Aging color shift still colors older traces.'),
        P('color_shift', 'Aging color shift', .65, 0, 1, .01, 'How much remembered color changes as the traces age.'),
        P('light', 'Brightness', 1., 0, 2, .01),
        P('background', 'Background light', .018, 0, .3, .01),
        P('softness', 'Optical softness', .8, 0, 6, .1, 'Pixels at a 720-pixel artwork edge.'),
        P('glow', 'Glow', .30, 0, 1, .01),
        P('mix', 'Mix', 1., 0, 1, .01),
    )),)


# Young highlights, intermediate pigment, and the cold residual memory.
PALETTES = np.asarray((
    ((1., .73, .29), (.91, .23, .15), (.04, .58, .60)),
    ((1., .62, .79), (.60, .17, .69), (.13, .31, .87)),
    ((.91, .97, .82), (.34, .77, .47), (.11, .39, .38)),
    ((1., .81, .54), (.83, .25, .10), (.24, .17, .28)),
), np.float32)


def _smooth(x):
    x = np.clip(x, 0., 1.)
    return x*x*(3-2*x)


def memory_pose(p, seconds):
    """Continuous, bounded path in artwork coordinates (independent of FPS)."""
    phase = math.tau*(seconds/p['period'] + p['phase'])
    # The derivative stays positive; variable pace never teleports the object.
    angle = phase + p['variation']*(.58*math.sin(phase-.6) + .17*math.sin(2*phase+.8))
    if p['path'] == 0:
        x, y = .77*math.cos(angle), math.sin(angle)
    elif p['path'] == 1:
        x, y = .83*math.sin(angle), .82*math.sin(2*angle)
    else:
        x = .67*math.sin(angle) + .20*math.sin(angle*.43+1.1)
        y = .62*math.sin(2*angle+.65) + .18*math.cos(angle*.71+.5)
    # Multiply the completed legacy path by neutral defaults so old documents
    # retain exact positions. Both the live object and its history use this pose.
    return (x*p['travel']*.5*(p.get('amplitude_x', 100.)/100.),
            y*p['travel']*.5*(p.get('amplitude_y', 100.)/100.),
            p['rotation']+p['spin']*seconds)


def memory_frame(p, size, seconds, preset):
    cw, ch = content_size(preset, size)
    dx, dy = object_offset(preset, size)
    x, y, angle = memory_pose(p, seconds*preset.get('speed', 1.))
    return (size[0]*.5+dx+x*cw, size[1]*.5+dy+y*ch), min(cw, ch)*p['size'], angle


def _stamp(canvas, center, radius, rotation, age, opacity, emitted, p, unit, seed_phase):
    """Draw only a trace's affected rectangle, with no full-canvas per-tap arrays."""
    h, w = canvas.shape[:2]
    erosion = p['dissolve']*age*age
    soft = max(.65, unit*(.7+erosion*11))
    extent = radius*(1+.16*erosion)+soft*3
    left, right = max(0, int(math.floor(center[0]-extent))), min(w, int(math.ceil(center[0]+extent+1)))
    top, bottom = max(0, int(math.floor(center[1]-extent))), min(h, int(math.ceil(center[1]+extent+1)))
    if right <= left or bottom <= top: return
    yy, xx = np.ogrid[top:bottom, left:right]
    # Subtract the artwork origin before narrowing precision. Translating the
    # canvas must not round a different absolute float32 center into each stamp.
    x = np.asarray((xx-center[0])/radius, np.float32)
    y = np.asarray((yy-center[1])/radius, np.float32)
    cs, sn = math.cos(math.radians(rotation)), math.sin(math.radians(rotation))
    u, v = x*cs+y*sn, -x*sn+y*cs
    # Erosion stays attached to the deposited form; no frame-random flickering.
    field = (np.sin(u*9+v*6+emitted*.8+seed_phase)
             + .5*np.sin(u*21-v*13-emitted*.43)
             + .25*np.cos(v*39+u*27+seed_phase)) / 1.75
    u = u + erosion*.10*np.sin(v*8+emitted*.7)
    v = v + erosion*.09*np.cos(u*11-emitted*.6)
    radial = np.hypot(u, v)
    metric = radial
    if p['shape'] == 2:
        sector = math.tau/p['sides']
        theta = np.arctan2(v, u)+math.pi*.5
        metric = radial*np.cos((theta+sector*.5)%sector-sector*.5)/math.cos(math.pi/p['sides'])
    distance = (metric-1)*radius
    mask = _smooth(.5-distance/(2*soft))
    if p['shape'] == 1:
        mask *= _smooth((radial-.69)*radius/(2*soft))
    mask *= np.clip(1-erosion*(.8+field*.95), 0, 1)
    palette = PALETTES[int(p['palette'])]
    phase = (emitted*p['color_speed'] + age*p['color_shift']*.65) % 1 * 3
    index = int(phase)
    blend = float(_smooth(phase-index))
    color = palette[index]*(1-blend)+palette[(index+1)%3]*blend
    shade = .38+.48*np.sqrt(np.clip(1-radial*radial, 0, 1))+.13*np.clip(-u-v, -1, 1)
    rim = np.exp(-((metric-.95)/(.025+.05*age))**2)
    highlight = np.exp(-((u+.30)**2+(v+.34)**2)/.08)*(1-age)*.32
    rgb = color[None,None,:]*shade[...,None] + rim[...,None]*color*.5 + highlight[...,None]
    # The oldest memories become delicate contours, with a faint colored body.
    mask *= (1-age*.72)+rim*age*.55
    alpha = np.clip(mask*opacity, 0, 1)[...,None]
    target = canvas[top:bottom, left:right]
    target[:] = target*(1-alpha)+np.clip(rgb*p['light'], 0, 1)*alpha


def _blur(arr, radius):
    image = Image.fromarray(np.uint8(np.clip(arr, 0, 1)*255))
    return np.asarray(image.filter(ImageFilter.GaussianBlur(radius)), np.float32)/255.


def render_image_memory(arr, p, seconds, preset):
    if p['mix'] <= 0: return arr
    h, w = arr.shape[:2]
    cw, ch = content_size(preset, (w,h)); unit = min(cw,ch)/720.
    dx, dy = object_offset(preset, (w,h))
    t = max(0., seconds*preset.get('speed', 1.))
    surface = np.zeros_like(arr, dtype=np.float32)
    seed_phase = (int(preset.get('seed', 0))%997)/997*math.tau
    history = p['persistence']
    if history > 0 and p['trail_opacity'] > 0:
        # Fixed, bounded quadrature: aging is continuous even if frame order or
        # timeline FPS changes. Birth/death ramps prevent popping at the ends.
        step = history/MAX_TRACES
        direction = math.radians(p['drift_angle'])
        for i in range(MAX_TRACES, 0, -1):
            lag = (i-.5)*step
            emitted = t-lag
            if emitted <= 0: continue
            age = lag/history
            fade = (1-_smooth(age)) * _smooth(emitted/.35)
            opacity = (1-math.exp(-step*9*p['trail_opacity']))*fade
            if opacity < .0002: continue
            x, y, angle = memory_pose(p, emitted)
            shift = p['drift']*lag*.065*min(cw,ch)
            center = (w*.5+dx+x*cw+shift*math.cos(direction),
                      h*.5+dy+y*ch+shift*math.sin(direction))
            radius = min(cw,ch)*p['size']*(1+p['expansion']*age)
            _stamp(surface, center, radius, angle, age, opacity, emitted, p, unit, seed_phase)
    center, radius, angle = memory_frame(p, (w,h), seconds, preset)
    _stamp(surface, center, radius, angle, 0., 1., t, p, unit, seed_phase)
    if p['softness'] > 0: surface = _blur(surface, p['softness']*unit)
    if p['glow'] > 0: surface += _blur(surface, 15*unit)*p['glow']
    result = np.clip(surface+p['background']*np.array((.64,.85,1.),np.float32), 0, 1)
    return np.asarray(arr*(1-p['mix'])+result*p['mix'], np.float32)
