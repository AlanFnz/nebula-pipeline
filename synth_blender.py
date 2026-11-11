"""Opt-in Blender source and reusable optical finishing; old studies stay local."""
import math
import numpy as np
from PIL import Image, ImageFilter

from synth_canvas import content_size, object_offset


def modules(Module, P):
    return (
        Module('blender_scene', 'Blender scene',
            'A procedural 3D sculpture rendered by Blender. Geometry, light and camera changes prepare new frames; cached frames are reused by preview and export.', (
            P('scene_version', 'Scene version', 1, 1, 1, 1, 'Versioned optical relic geometry.'),
            P('ring_width', 'Hoop width', 1., .4, 1.6, .01),
            P('tube_radius', 'Hoop thickness', .085, .025, .20, .005),
            P('hoop_bow', 'Hoop depth', .28, 0., .6, .01),
            P('hoop_twist', 'Hoop twist', .10, -.3, .3, .01),
            P('body_height', 'Assembly height', 1., .65, 1.3, .01),
            P('base_width', 'Pedestal width', 1., .5, 1.5, .01),
            P('crown_size', 'Crown size', 1., .3, 1.5, .01),
            P('axle_length', 'Side pin length', 1., .4, 1.5, .01),
            P('period', 'Rotation period', 6., .5, 60., .1, 'Seconds per full turn at global speed 1. The two sides of the sculpture repeat after half a turn.'),
            P('phase', 'Starting turn', 0., 0., 1., .01),
            P('direction', 'Direction', 0, 0, 1, 1, choices=('Forward', 'Reverse')),
            P('ease', 'Turn easing', .6, 0., .95, .01, 'Slows near the frontal views without stopping or reversing.'),
            P('size', 'Framing size', 1., .5, 1.5, .01),
            P('camera_yaw', 'Camera angle', 0., -60., 60., 1.),
            P('camera_elevation', 'Camera elevation', 10., 0., 45., 1.),
            P('metal_hue', 'Material hue', .15, 0., 1., .01),
            P('metal_saturation', 'Material saturation', .15, 0., 1., .01),
            P('metallic', 'Metallic', .8, 0., 1., .01),
            P('roughness', 'Roughness', .28, .05, .9, .01),
            P('environment', 'Environment light', .7, .01, 2., .01),
            P('reflection_contrast', 'Dark reflection', 1., 0., 1., .01),
            P('background_hue', 'Background hue', .40, 0., 1., .01),
            P('background_saturation', 'Background saturation', .58, 0., 1., .01),
            P('light_angle', 'Light angle', -45., -180., 180., 1.),
            P('light_size', 'Light softness', 4., .5, 8., .1),
            P('light_power', 'Light strength', 1000., 100., 3000., 25.),
            P('exposure', 'Exposure', .4, -3., 3., .05),
        )),
        Module('optical_diffusion', 'Optical diffusion',
            'Photographic softness, broad highlight diffusion and fine grain. Works after any generated object or imported footage.', (
            P('softness', 'Focus softness', 2.2, 0., 8., .1, 'Pixels at a 720-pixel artwork width.'),
            P('bloom', 'Highlight diffusion', .22, 0., 1., .01),
            P('radius', 'Diffusion radius', 18., 2., 60., 1.),
            P('warmth', 'Highlight warmth', .12, 0., 1., .01),
            P('grain', 'Fine grain', .026, 0., .1, .001),
            P('vignette', 'Edge shading', .12, 0., .8, .01),
            P('period', 'Texture loop', 6., .5, 60., .1),
            P('mix', 'Mix', 1., 0., 1., .01),
        )),
    )


MOTION_KEYS = frozenset(('period', 'phase', 'direction', 'ease', 'effect_intensity'))


def rotation(seconds, p, speed=1.):
    # Both bowed hoops retain half-turn symmetry. Normalize it before rounding
    # so the three cycles in the reference reuse the identical clean renders.
    phase = round((seconds*speed/p['period'] + p['phase']) % .5, 10) % .5
    angle = math.tau*phase - p['ease']*.5*math.sin(2*math.tau*phase)
    return round(angle * (-1 if p['direction'] else 1), 9)


def render_blender_scene(arr, p, seconds, preset):
    from synth_blender_bridge import render_frame
    h, w = arr.shape[:2]
    cw, ch = content_size(preset, (w,h))
    dx, dy = object_offset(preset, (w,h))
    parameters = {k:v for k,v in p.items() if k not in MOTION_KEYS}
    # Frame the same physical scene when the canvas is resized or repositioned.
    parameters.update(framing_height=h/max(1.,ch), offset_x=dx/w, offset_y=dy/h)
    image = render_frame(parameters, rotation(seconds, p, preset['speed']), (w,h))
    return np.asarray(image, np.float32)/255.


def _blur(arr, radius):
    return np.asarray(Image.fromarray(np.uint8(np.clip(arr,0,1)*255)).filter(
        ImageFilter.GaussianBlur(radius)), np.float32)/255.


def render_optical_diffusion(arr, p, seconds, preset, index=0):
    if not p['mix']: return arr
    h,w = arr.shape[:2]
    cw,ch = content_size(preset, (w,h)); unit = min(cw/720.,ch/960.)
    out = _blur(arr, p['softness']*unit) if p['softness'] else arr.copy()
    if p['bloom']:
        highlights = np.clip((out-.35)/.65,0,1)
        glow = _blur(highlights, p['radius']*unit)*p['bloom']
        glow *= np.array((1.,1.-p['warmth']*.15,1.-p['warmth']*.45),np.float32)
        out = out+(1-out)*glow
    if p['vignette']:
        yy,xx = np.mgrid[:h,:w].astype(np.float32)
        radius = ((xx/w-.5)*1.4)**2+((yy/h-.5)*1.4)**2
        out *= (1-p['vignette']*radius)[...,None]
    if p['grain']:
        phase = round((seconds*preset['speed']/p['period']) % 1.,10) % 1.
        rng = np.random.default_rng(int(preset['seed'])+int(phase*100000))
        noise = rng.normal(0,p['grain']*min(1.,unit),(h,w,1)).astype(np.float32)
        out += noise*(.4+.6*np.sqrt(np.clip(out,0,1)))
    return arr*(1-p['mix'])+np.clip(out,0,1)*p['mix']
