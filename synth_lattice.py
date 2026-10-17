"""Optical lattice: fixed cells, traveling size waves and curved spectral light.

A procedural source, independent of output size or preview history. Distances
use one artwork scale on both axes so reframing cannot stretch the cells.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageFilter

from synth_canvas import content_size, object_offset


def modules(Module, P):
    return (Module('chromatic_lattice', 'Chromatic lattice',
        'A fixed grid of luminous shapes with traveling size and color waves. Change the shapes, wave geometry, palette and optical finish independently.', (
        P('shape', 'Cell shape', 0, 0, 3, 1, choices=('Circle', 'Square', 'Diamond', 'Polygon')),
        P('sides', 'Polygon sides', 6, 3, 12, 1),
        P('spacing', 'Cell spacing', 79.2, 24, 240, .5, 'Pixels at a 720-pixel artwork edge. The grid stays evenly spaced when the canvas changes.'),
        P('size', 'Maximum size', .94, .1, 1., .01, 'Cell diameter relative to spacing. Small gaps keep neighboring shapes distinct.'),
        P('minimum', 'Minimum size', 0., 0, 1, .01, 'Smallest size during a pulse. Zero lets a cell disappear completely.'),
        P('rotation', 'Cell rotation', 0., -180, 180, 1),
        P('wave_shape', 'Wave shape', 0, 0, 2, 1, choices=('Diamond rings', 'Circular rings', 'Parallel bands')),
        P('wavelength', 'Wave spacing', 10., 2, 30, .1, 'Cell intervals between neighboring size minima.'),
        P('period', 'Pulse period', 5., .3, 30, .1, 'Seconds between size pulses at global speed 1. Color has its own cycle.'),
        P('phase', 'Starting phase', 0., 0, 1, .01),
        P('direction', 'Travel direction', 0, 0, 1, 1, choices=('Inward', 'Outward')),
        P('angle', 'Band angle', 45., -180, 180, 1, 'Direction used by Parallel bands.'),
        P('pulse', 'Pulse depth', 1., 0, 1, .01, 'Zero holds every cell at Maximum size; color can keep moving.'),
        P('palette', 'Palette', 0, 0, 3, 1, choices=('Neon spectrum', 'Ember / rose', 'Lagoon / violet', 'Pearl / silver')),
        P('color_period', 'Color cycle', 10., 1, 60, .1),
        P('color_phase', 'Color phase', 0., 0, 1, .01),
        P('color_spread', 'Color wave depth', .8, 0, 2, .01, 'Spread color changes from the center through neighboring cells.'),
        P('gradient', 'Color across each cell', .8, 0, 2, .01, 'Curved bands of light within each shape. Zero gives flat color.'),
        P('saturation', 'Color saturation', 1., 0, 1.5, .01),
        P('light', 'Brightness', 1., 0, 2, .01),
        P('rim', 'Luminous rim', .40, 0, 1, .01),
        P('softness', 'Optical softness', 1.4, 0, 5, .1, 'Pixels at a 720-pixel artwork edge.'),
        P('glow', 'Glow amount', 1.2, 0, 2, .01),
        P('glow_radius', 'Glow spread', 16., 1, 30, .5, 'Pixels at a 720-pixel artwork edge.'),
        P('grain', 'Fine grain', .009, 0, .1, .001),
        P('background', 'Background brightness', 0., 0, .3, .01),
        P('mix', 'Mix', 1., 0, 1, .01),
    )),)


# Three optical moods per palette; each has a cool face, transition and warm
# edge. Keeping the gradient direction stable avoids flipping the light when
# the palette travels through cyan and amber.
PALETTES = np.asarray((
    (((.28,.22,.60),(.92,.015,.35),(1.,.015,.07)),
     ((.24,.28,.70),(.08,.70,.70),(1.,.65,.035)),
     ((1.,.66,.055),(1.,.24,.015),(.96,.015,.025))),
    (((.35,.10,.43),(.93,.06,.29),(1.,.35,.08)),
     ((.64,.24,.48),(1.,.52,.39),(1.,.81,.42)),
     ((.97,.59,.13),(.90,.14,.06),(.54,.025,.09))),
    (((.25,.10,.65),(.09,.48,.76),(.10,.88,.78)),
     ((.40,.25,.77),(.22,.71,.80),(.70,.89,.66)),
     ((.44,.74,.86),(.36,.30,.68),(.16,.07,.38))),
    (((.28,.34,.43),(.57,.66,.73),(.88,.91,.89)),
     ((.59,.63,.68),(.83,.87,.88),(.94,.89,.78)),
     ((.80,.80,.76),(.45,.49,.55),(.17,.21,.29))),
), dtype=np.float32)


def lattice_frame(p, size, preset):
    w,h=size
    cw,ch=content_size(preset,size)
    unit=max(1.,min(cw,ch))/720.
    dx,dy=object_offset(preset,size)
    return (w*.5+dx,h*.5+dy),p['spacing']*unit,unit


def wave_distance(x,y,p):
    if p['wave_shape']==1:
        return np.hypot(x,y)
    if p['wave_shape']==2:
        angle=np.deg2rad(p['angle'])
        return x*np.cos(angle)+y*np.sin(angle)
    return np.abs(x)+np.abs(y)


def pulse_size(distance, seconds, p):
    direction=1. if p['direction']==0 else -1.
    wave=np.abs(np.sin(np.pi*(distance/p['wavelength']+direction*seconds/p['period']+p['phase'])))
    return 1-p['pulse']+p['pulse']*(p['minimum']+(1-p['minimum'])*wave)


def cell_colors(distance, clock, p):
    cycle=np.mod(clock+p['color_spread']*.7*np.sin(2*np.pi*clock)*np.exp(-np.abs(distance)*.55),1)
    stops=np.array((0.,.12,.32,.38,.54,.62,1.))
    moods=np.array((0,1,1,2,2,0,0))
    index=np.clip(np.searchsorted(stops,cycle,side='right')-1,0,len(stops)-2)
    blend=(cycle-stops[index])/(stops[index+1]-stops[index])
    blend=np.asarray(blend*blend*(3-2*blend),np.float32)
    colors=PALETTES[int(p['palette'])]
    a,b=colors[moods[index]],colors[moods[index+1]]
    f=blend[...,None,None]
    rgb=a*(1-f)+b*f
    value=a.max(-1)*(1-blend[...,None])+b.max(-1)*blend[...,None]
    sat_a=1-a.min(-1)/np.maximum(a.max(-1),1e-6)
    sat_b=1-b.min(-1)/np.maximum(b.max(-1),1e-6)
    saturation=sat_a*(1-blend[...,None])+sat_b*blend[...,None]
    lo=rgb.min(-1,keepdims=True); span=rgb.max(-1,keepdims=True)-lo
    chroma=(rgb-lo)/np.maximum(span,1e-6)
    return np.asarray(value[...,None]*(1-saturation[...,None]+chroma*saturation[...,None]),np.float32)


def _blur(arr, radius):
    return np.asarray(Image.fromarray(np.uint8(np.clip(arr,0,1)*255)).filter(ImageFilter.GaussianBlur(radius)),dtype=np.float32)/255


def _cell_surface(p, t, center, spacing, w, top, bottom):
    y,x=np.mgrid[top:bottom,:w].astype(np.float32)
    # Odd columns and half-cell rows match the reference composition. This
    # origin stays fixed when extending the canvas around the artwork.
    gx=(x-center[0])/spacing
    gy=(y-center[1])/spacing
    ix=np.floor(gx+.5);iy=np.floor(gy)+.5
    distance=wave_distance(ix,iy,p)
    radius=.5*spacing*p['size']*pulse_size(distance,t,p)
    qx=(gx-ix)*spacing/np.maximum(radius,.001)
    qy=(gy-iy)*spacing/np.maximum(radius,.001)
    angle=np.deg2rad(p['rotation']);cs=np.cos(angle);sn=np.sin(angle)
    u=qx*cs+qy*sn;v=-qx*sn+qy*cs
    shape=int(p['shape'])
    if shape==0: metric=np.hypot(u,v)
    elif shape==1: metric=np.maximum(np.abs(u),np.abs(v))*np.sqrt(2.)
    elif shape==2: metric=np.abs(u)+np.abs(v)
    else:
        n=int(p['sides']);sector=2*np.pi/n
        theta=np.arctan2(v,u)+np.pi/2
        metric=np.hypot(u,v)*np.cos((theta+sector*.5)%sector-sector*.5)/np.cos(np.pi/n)
    edge=(metric-1)*radius
    mask=np.clip(.5-edge,0,1)
    mask*=radius>.01
    # Slow color interference moves through the fixed grid. Each cell carries
    # a bent spectral band with a consistent cool-to-warm light direction.
    clock=t/p['color_period']+p['color_phase']
    colors=cell_colors(distance,clock,p)
    curved=np.clip(.43+p['gradient']*((v-u)*.45-.22*(u*u+v*v)),0,1)
    curved=np.clip((curved-.20)/.62,0,1)
    segment=curved>=.5
    blend=np.where(segment,(curved-.5)*2,curved*2)
    blend=blend*blend*(3-2*blend)
    low=np.where(segment[...,None],colors[...,1,:],colors[...,0,:])
    high=np.where(segment[...,None],colors[...,2,:],colors[...,1,:])
    color=low*(1-blend[...,None])+high*blend[...,None]
    # A bright curved edge gives the cells a lens-like appearance.
    rim=np.exp(-((metric-.97)/.045)**2)*p['rim']
    color=color*(.91+.09*np.sqrt(np.clip(1-(u*u+v*v)*.45,0,1)))[...,None]
    color+=rim[...,None]*np.array((.35,.32,.42),np.float32)
    lum=color@np.array((.2126,.7152,.0722),np.float32)
    color=lum[...,None]+(color-lum[...,None])*p['saturation']
    return np.asarray(np.clip(color,0,1)*mask[...,None],np.float32)


def render_chromatic_lattice(arr,p,seconds,preset):
    if not p['mix']: return arr
    h,w=arr.shape[:2]
    center,spacing,unit=lattice_frame(p,(w,h),preset)
    t=float(seconds)*preset.get('speed',1.)
    # Bound intermediate color/shading arrays even on a 4K canvas.
    surface=np.empty_like(arr,dtype=np.float32)
    for top in range(0,h,128):
        surface[top:top+128]=_cell_surface(p,t,center,spacing,w,top,min(h,top+128))
    if p['softness']: surface=_blur(surface,p['softness']*unit)
    if p['glow']: surface+=_blur(surface,p['glow_radius']*unit)*p['glow']
    result=np.full_like(arr,p['background'])+surface*p['light']
    if p['grain']:
        rng=np.random.default_rng((int(preset['seed'])+int(np.floor(t*30))*7919)%(2**32))
        result+=rng.normal(0,p['grain'],(h,w,1)).astype(np.float32)*np.sqrt(np.clip(result,0,1))
    return np.asarray(arr*(1-p['mix'])+np.clip(result,0,1)*p['mix'],np.float32)
