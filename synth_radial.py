"""Stateless polar-domain blooms: nested crowns, branching contours and rays.

Coordinates use one reference scale on both axes. Angular harmonics are integer
multiples so the polar seam is continuous. Every frame is independent of seeks.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageFilter

from synth_canvas import content_size, object_offset


def modules(Module, P):
    return (Module('radial_bloom', 'Radial bloom',
        'Expanding nested crowns with branching contours, drifting color and a moving center.', (
        P('expansion', 'Expansion', 1., .3, 3., .01, 'Scale the complete pattern. Audio can gently pulse this without changing the flow clock.'),
        P('petals', 'Petals', 18, 3, 48, 1),
        P('detail', 'Branch detail', .72, 0, 1, .01, 'Fine branching along the petal edges.'),
        P('branching', 'Branch depth', .65, 0, 1, .01),
        P('flow', 'Outward flow', .85, 0, 3, .01, 'Continuous expansion rate. Zero holds the radial flow.'),
        P('variation', 'Flow variation', .9, 0, 1, .01, 'Uneven acceleration and changing contour depth.'),
        P('rotation', 'Rotation speed', 1.2, -30, 30, .1, 'Degrees per second.'),
        P('phase', 'Starting phase', .12, 0, 1, .01),
        P('center_drift', 'Center drift', .28, 0, 1, .01),
        P('drift_speed', 'Drift speed', .3, 0, 2, .01),
        P('palette', 'Palette', 0, 0, 2, 1, choices=('Dusty cyan / rose', 'Violet / ember', 'Silver / ink')),
        P('color_phase', 'Color phase', .0, 0, 1, .01),
        P('color_speed', 'Color drift', .018, 0, .3, .001),
        P('light', 'Light', 1., 0, 2, .01),
        P('softness', 'Optical softness', 1.8, 0, 8, .1, 'Pixels at the artwork reference width. Softens contours like a filmed display.'),
        P('grain', 'Film grain', .026, 0, .2, .001),
        P('vibration', 'Ray vibration', 0., 0, 2, .01, 'Bend the rays around their shared origin. Waves travel outward along the rays without shifting the canvas or its center. Audio can drive this intensity.'),
        P('vibration_speed', 'Vibration speed', 7., 0, 12, .1, 'Oscillations per second at global speed 1. Zero holds the wave deformation.'),
        P('vibration_wavelength', 'Wave length', .26, .05, 1, .01, 'Distance between bends as a fraction of the artwork reference edge. Smaller values make tighter ripples.'),
        P('vibration_irregularity', 'Ray independence', .65, 0, 1, .01, 'Vary the phase around the center so neighboring rays do not all sway together.'),
    )),)


PALETTES = (
    ((.16,.22,.29),(.29,.34,.43),(.40,.43,.59),(.58,.44,.64),
     (.69,.51,.62),(.37,.64,.75),(.66,.73,.76),(.75,.74,.68),(.29,.48,.61)),
    ((.12,.10,.23),(.32,.20,.41),(.59,.26,.52),(.85,.40,.45),
     (.92,.64,.43),(.64,.45,.62),(.48,.43,.67),(.70,.65,.78),(.25,.28,.48)),
    ((.08,.11,.15),(.20,.24,.28),(.42,.46,.51),(.71,.74,.75),
     (.86,.85,.81),(.59,.64,.67),(.33,.40,.45),(.69,.75,.76),(.18,.23,.28)),
)


def radial_frame(p, size, seconds, preset):
    w, h = size
    cw, ch = content_size(preset, (w, h))
    unit = max(1., min(cw, ch))
    ox, oy = object_offset(preset, (w, h))
    t = float(seconds) * preset.get('speed', 1.)
    drift = p['center_drift'] * unit
    dt = t * p['drift_speed']
    cx = w*.5 + ox + drift*(.72*np.cos(dt+.32) + .23*np.sin(dt*1.73))
    cy = h*.5 + oy + drift*(.52*np.sin(dt*.77-.25))
    return (cx, cy), unit


def vibrating_angle(angle, radius, seconds, p):
    """Angular deformation only: the origin and radial distances stay fixed.

    Retarded wave phase travels toward larger radii. Integer angular harmonics
    keep the polar seam continuous; no history or frame-rate state is involved.
    """
    strength = p.get('vibration', 0.)
    if not strength:
        return angle
    clock = seconds * p.get('vibration_speed', 7.)
    phase = 2*np.pi*(clock-radius/p.get('vibration_wavelength', .26))
    irregularity = p.get('vibration_irregularity', .65)
    wave = np.sin(phase + irregularity*1.6*np.sin(3*angle+.17*clock))
    wave += .35*irregularity*np.sin(phase*.61+2*np.cos(5*angle)-.31*clock)
    # Relative to petal spacing, so adding petals does not fold the rays over.
    return angle + strength*1.25/p['petals']*wave/(1+.35*irregularity)


def render_radial_bloom(arr, p, seconds, preset):
    h, w = arr.shape[:2]
    (cx, cy), unit = radial_frame(p, (w, h), seconds, preset)
    t = float(seconds) * preset.get('speed', 1.)
    y, x = np.mgrid[:h, :w].astype(np.float32)
    x = (x-cx)/unit; y = (y-cy)/unit
    radius = np.maximum(np.hypot(x,y), .35/unit)
    angle = np.arctan2(y,x) - np.deg2rad(p['rotation'])*t
    angle = vibrating_angle(angle, radius, t, p)
    # Integrated variable speed stays monotonic, avoiding a reversing zoom.
    travel = p['flow']*(t + p['variation']*.34*np.sin(t*1.65)/1.65)
    u = np.log(radius/(.05*p['expansion'])) - travel + p['phase']*2.65
    v = angle*p['petals'] + .16*np.sin(u*1.7+t*.11)
    pulse = 1-p['variation']*(.5-.5*np.cos(t*1.45))
    field = u + pulse*(.24+.10*p['branching'])*np.cos(v)
    for octave in range(1, 6):
        frequency = 3**octave
        # Fade subpixel contour harmonics before they alias at the center.
        footprint = radius*unit/(p['petals']*frequency)
        visible = np.clip(footprint*.8, 0, 1)
        amplitude = p['branching']*pulse/frequency*(.28+.9*p['detail'])
        field += visible*amplitude*np.sin(v*frequency +
                    np.sin(field*frequency*4+t*.12)*1.8)
    tooth = np.abs(np.sin(v*.5))
    field += pulse*(.11+.10*p['branching'])*np.log(np.maximum(tooth,.008))
    forks = np.abs(tooth-.16*np.abs(np.sin(u*4)))
    field -= pulse*p['detail']*.07*np.log(np.maximum(forks,.006))
    colors = np.asarray(PALETTES[int(p['palette'])], dtype=np.float32)
    coordinate = field*3.35 + 9*(p['color_phase']+p['color_speed']*t)
    index = np.floor(coordinate).astype(np.int32)
    fraction = (coordinate-index)[...,None]
    # Soft bands keep the film-like color fields while the contours branch.
    fraction = fraction*fraction*(3-2*fraction)
    result = colors[index%len(colors)]*(1-fraction)+colors[(index+1)%len(colors)]*fraction
    contour = np.exp(-(np.sin(field*np.pi)/.065)**2)[...,None]
    result = result*(1-.16*contour)+np.array((.50,.63,.68))*contour*.16
    # Between crowns, airy rays carry the movement through a washed field.
    ray_phase = 1-pulse
    haze = .52+np.stack((.06*np.sin(u*.8), .035*np.cos(u*.7), .08*np.cos(u*.6)),axis=-1)
    result = result*(1-ray_phase*.55)+haze*(ray_phase*.55)
    ray = np.exp(-(tooth/.025)**2)[...,None]
    fringe = np.exp(-(np.abs(np.sin((v+.10)*.5))/.06)**2)[...,None]
    result += ray_phase*(ray*np.array((.13,.23,.25))+fringe*np.array((.10,-.025,.015)))
    if p['softness']:
        image = Image.fromarray(np.uint8(np.clip(result*255,0,255)))
        image = image.filter(ImageFilter.GaussianBlur(p['softness']*unit/720))
        result = np.asarray(image, dtype=np.float32)/255
    if p['grain']:
        rng = np.random.default_rng((int(preset['seed'])+int(np.floor(t*30))*7919)%(2**32))
        noise = rng.normal(0,p['grain'],(h,w,1)).astype(np.float32)
        result = result + noise*(.35+.65*np.sqrt(np.maximum(result,0)))
    return np.asarray(result*p['light'], dtype=np.float32)
