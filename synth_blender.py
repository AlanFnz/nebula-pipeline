"""Opt-in Blender source and reusable optical finishing; old studies stay local."""
import math
import json
from pathlib import Path
from functools import lru_cache
from bisect import bisect_right
from types import SimpleNamespace
import numpy as np
from PIL import Image, ImageFilter

from synth_canvas import content_size, object_offset
from synth_blender_parts import parameters as part_parameters, part_poses


def modules(Module, P):
    return (
        Module('blender_scene', 'Blender scene',
            'A procedural 3D sculpture rendered by Blender. Geometry, light and camera changes prepare new frames; cached frames are reused by preview and export.', (
            P('scene', 'Sculpture', 0, 0, 1, 1, choices=('Optical relic', 'Orbital rings')),
            P('scene_version', 'Scene version', 1, 1, 1, 1, 'Versioned procedural sculpture geometry.'),
            P('ring_width', 'Hoop width', 1., .4, 1.6, .01),
            P('tube_radius', 'Hoop thickness', .085, .025, .20, .005),
            P('hoop_bow', 'Hoop depth', .28, 0., .6, .01),
            P('hoop_twist', 'Hoop twist', .10, -.3, .3, .01),
            P('body_height', 'Assembly height', 1., .65, 1.3, .01),
            P('base_width', 'Pedestal width', 1., .5, 1.5, .01),
            P('crown_size', 'Crown size', 1., .3, 1.5, .01),
            P('axle_length', 'Side pin length', 1., .4, 1.5, .01),
            P('period', 'Rotation period', 6., .5, 60., .1, 'Seconds per full turn at global speed 1. The original symmetric sculpture repeats after half a turn; edited pieces can require a full turn.'),
            P('phase', 'Starting turn', 0., 0., 1., .01),
            P('direction', 'Direction', 0, 0, 1, 1, choices=('Forward', 'Reverse')),
            P('ease', 'Turn easing', .6, 0., .95, .01, 'Slows near the frontal views without stopping or reversing.'),
            P('motion_exposure', 'Motion exposure', 0., 0., .5, .01, 'Blend a delayed 3D exposure into the current pose. Clean cached frames are reused.'),
            P('exposure_delay', 'Exposure delay', .125, .01, 1., .005, 'Seconds between the two exposures at global speed 1.'),
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
        ) + orbital_parameters(P) + part_parameters(P)),
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



# Opt-in additions are stripped from the v1 source request, preserving its cache.
def orbital_parameters(P):
    settings = [
        P('pose_steps', 'Poses per loop', 60, 0, 120, 1, 'Zero is continuous. The reference uses 60 held poses per loop; other counts create a different stop-motion cadence.'),
        P('orbit_tumble', 'Precessing motion', 1., 0., 1., .01, 'Blend the authored three-axis motion with simple axial rotation.'),
        P('band_width', 'Ring band width', .25, .08, .40, .01),
        P('band_depth', 'Ring depth', .16, .04, .4, .01),
        P('ring_gap', 'Ring spacing', .055, .01, .18, .005),
        P('edge_radius', 'Edge rounding', .045, .0, .1, .005),
        P('core_size', 'Center sphere size', .32, .1, .5, .01),
        P('paint_light', 'Paint brightness', .66, .05, 1., .01),
        P('accent_hue', 'Ivory hue', .12, 0., 1., .01),
        P('accent_saturation', 'Ivory saturation', .18, 0., 1., .01),
        P('accent_light', 'Ivory brightness', .88, .05, 1., .01),
        P('surface_grain', 'Paint texture', .5, 0., 1., .01),
        P('sky_light', 'Sky brightness', .48, .05, 1., .01),
        P('ground_hue', 'Ground hue', .21, 0., 1., .01),
        P('ground_saturation', 'Ground saturation', .65, 0., 1., .01),
        P('ground_light', 'Ground brightness', .36, .05, 1., .01),
        P('stage_motion', 'Landscape movement', .6, 0., 2., .05, 'Looping drift of the painted background bands.'),
        P('stage_bands', 'Landscape bands', .45, 0., 1., .01),
        P('horizon_depth', 'Horizon distance', 7., 1., 30., .1),
    ]
    for i,(turns,phase,tilt) in enumerate(((3,0,0),(1,0,0),(1,0,0),(1,0,0),(1,0,0)),1):
        settings.extend((P('orbit_turns_'+str(i),f'Ring {i} · Orbit turns',turns,-8,8,1,
                           'Turns per shared loop. Zero stops this ring; a negative value reverses it.'),
                         P('orbit_phase_'+str(i),f'Ring {i} · Orbit phase',phase,-180.,180.,1.),
                         P('orbit_tilt_'+str(i),f'Ring {i} · Axis tilt',tilt,-90.,90.,1.)))
    return tuple(settings)


ORBITAL_KEYS = frozenset(p.key for p in orbital_parameters(lambda key,*a,**kw:SimpleNamespace(key=key)))

MOTION_KEYS = frozenset(('period', 'phase', 'direction', 'ease', 'effect_intensity','motion_exposure','exposure_delay'))


def rotation(seconds, p, speed=1., *, symmetric=True):
    # The untouched sculpture has half-turn symmetry. Reuse its original clean
    # frames, but retain the full turn when individual edits break that symmetry.
    cycle = .5 if symmetric else 1.
    phase = round((seconds*speed/p['period'] + p['phase']) % cycle, 10) % cycle
    angle = math.tau*phase - p['ease']*.5*math.sin(2*math.tau*phase)
    return round(angle * (-1 if p['direction'] else 1), 9)


def render_blender_scene(arr, p, seconds, preset):
    from synth_blender_bridge import render_frame
    h, w = arr.shape[:2]
    cw, ch = content_size(preset, (w,h))
    dx, dy = object_offset(preset, (w,h))
    parameters = {k:v for k,v in p.items() if k not in MOTION_KEYS and not k.startswith('part_')}
    # Frame the same physical scene when the canvas is resized or repositioned.
    if not p.get('scene',0):
        parameters = {k:v for k,v in parameters.items() if k not in ORBITAL_KEYS and k != 'scene'}
    parameters.update(framing_height=h/max(1.,ch), offset_x=dx/w, offset_y=dy/h)
    def sample(time):
        parts = part_poses(p,time,preset['speed'])
        angle = rotation(time,p,preset['speed'],symmetric=not parts and not p.get('scene',0))
        if p.get('scene',0): angle = stepped_orbit(angle,p.get('pose_steps',0))
        image = render_frame(parameters,angle,(w,h),parts=parts) if parts else render_frame(parameters,angle,(w,h))
        return np.asarray(image,np.float32)/255.
    out=sample(seconds)
    amount=p.get('motion_exposure',0.)
    if amount:
        previous=sample(seconds-p['exposure_delay']/max(1e-8,preset['speed']))
        out=out*(1-amount)+previous*amount
    return out


@lru_cache(maxsize=1)
def orbital_steps():
    return tuple(json.loads((Path(__file__).parent/'assets/blender/orbital-motion-v1.json').read_text())['steps'])


def stepped_orbit(angle, count):
    if not count:return angle
    phase=(angle/math.tau)%1.
    if count == 60:
        steps=orbital_steps();phase=steps[max(0,bisect_right(steps,phase+1e-8)-1)]
    else:phase=math.floor(phase*count+1e-8)/count
    return round(phase*math.tau,9)


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
