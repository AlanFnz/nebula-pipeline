"""Raised optical pleats, sampled from absolute time without image feedback.

Ray/height-field intersections give the folds real occlusion. The camera and
mirror coordinates are independent of the phosphor finish, so changing the
geometry never magnifies the screen grid. No reference frames are embedded.
"""
from __future__ import annotations

import colorsys
import math
import numpy as np
from PIL import Image, ImageFilter

from synth_canvas import content_size, object_offset


def modules(Module, P):
    return (Module('pleated_field', 'Pleated field',
        'A raised, repeating surface seen through mirrored optical folds. Camera moves, relief, symmetry, aperture and color remain independent.', (
        P('profile', 'Fold profile', 0, 0, 3, 1, choices=('Soft pleats', 'Scallops', 'Cushions', 'Folded tiles')),
        P('density', 'Fold density', 5., 1, 18, .1),
        P('depth', 'Relief depth', .55, 0, 1.4, .01),
        P('curl', 'Fold curl', .18, 0, .4, .01),
        P('stagger', 'Row stagger', .14, 0, .5, .01),
        P('size', 'Scale', 1., .02, 8, .01),
        P('projection', 'Camera model', 0, 0, 1, 1, choices=('Original optical plane', 'Perspective relief')),
        P('yaw', 'Camera orbit X', 0., -75, 75, 1),
        P('pitch', 'Camera orbit Y', 0., -75, 75, 1),
        P('distance', 'Perspective distance', 2., .5, 8, .01),
        P('mirror_x', 'Mirror center X', 0., -1.5, 1.5, .01),
        P('mirror_y', 'Mirror center Y', 0., -1.5, 1.5, .01),
        P('angle', 'Camera angle', 18., -720, 720, 1),
        P('perspective', 'Perspective', .5, -.9, .9, .01),
        P('shear', 'Fold slant', .25, -2, 2, .01),
        P('tilt_x', 'Relief view X', .8, -1.5, 1.5, .01),
        P('tilt_y', 'Relief view Y', -.25, -1.5, 1.5, .01),
        P('symmetry', 'Mirrors', 0, 0, 3, 1, choices=('None', 'Top / bottom', 'Four quadrants', 'Left / right')),
        P('pan_x', 'Surface travel X', 0., -30, 30, .01),
        P('pan_y', 'Surface travel Y', 0., -30, 30, .01),
        P('aperture', 'Visible field', 3., 0, 6, .01, 'Reduce to gather the surface into a small central figure. A large value fills the canvas.'),
        P('taper', 'Field taper', .6, 0, 2, .01),
        P('boundary', 'Field outline', 0, 0, 2, 1, choices=('Diamond', 'Ellipse', 'Rectangle')),
        P('edge', 'Side position', 0., -3, 3, .01, 'Move the outer boundary in the one-sided mirror view.'),
        P('phase', 'Fold phase', 0., -30, 30, .01),
        P('flow', 'Surface flow', .16, -2, 2, .01, 'Cycles per second, independent of the camera choreography.'),
        P('cadence', 'Motion FPS', 12., 1, 60, 1),
        P('palette', 'Palette', 0, 0, 4, 1, choices=('Violet / tangerine', 'Teal / coral', 'Ink / parchment', 'Rose / midnight', 'Filmed violet / orange')),
        P('hue_shift', 'Palette rotation', 0., -1, 1, .01),
        P('saturation', 'Saturation', 1., 0, 1.5, .01),
        P('light', 'Exposure', 1., 0, 2, .01),
        P('highlight', 'Fold highlights', 1.1, 0, 1.5, .01),
        P('light_angle', 'Relief light direction', 20., -180, 180, 1),
        P('background_motion', 'Background drift', .85, 0, 1, .01),
        P('irregularity', 'Surface irregularity', .55, 0, 1, .01),
        P('seams', 'Fold shadows', .55, 0, 1, .01),
        P('softness', 'Optical softness', 3.4, 0, 8, .1, 'Pixels at a 720-pixel artwork edge. Screen texture is a separate effect.'),
        P('mix', 'Opacity', 1., 0, 1, .01),
    )),)


PALETTES = (
    ((.32,.14,.88), (1.,.58,.78), (1.,.40,.035), (1.,.255,.015), (.96,.015,.46)),
    ((.015,.49,.53), (.72,.97,.84), (1.,.63,.33), (.94,.27,.18), (.63,.09,.28)),
    ((.13,.12,.19), (.80,.77,.66), (.42,.36,.27), (.83,.79,.67), (.56,.49,.43)),
    ((.67,.035,.36), (.97,.67,.61), (.49,.21,.83), (.055,.03,.15), (.19,.07,.36)),
    ((.43,.27,.92), (1.,.64,.76), (1.,.40,.035), (1.,.27,.02), (.97,.02,.50)),
)


def _height(u, v, p):
    a = math.tau*(u + p['stagger']*np.sin(math.tau*v))
    b = math.tau*v
    if p['profile'] == 3:
        # Broad faces with rounded creases, rather than a continuously snaking
        # ribbon. The triangular row offset gives each face a distinct corner.
        row=(2/math.pi)*np.arcsin(np.sin(b))
        a=math.tau*(u+p['stagger']*row)
        z=.34*(.8*(2/math.pi)*np.arcsin(np.sin(a))+.2*np.sin(a))+p['curl']*np.cos(b)
    elif p['profile'] == 1:
        z = .34*np.sin(a)*(.7+.3*np.cos(b)) + p['curl']*.7*np.sin(b)
    elif p['profile'] == 2:
        z = .65*(.5+.5*np.cos(a))**.3*(.5+.5*np.cos(b))**.5-.3
    else:
        z = .34*(.65*np.tanh(2.2*np.sin(a))+.35*(2/math.pi)*np.arcsin(np.sin(a))) + p['curl']*np.sin(b)
    return z*p['depth']


def _palette(p):
    colors = np.asarray(PALETTES[int(p['palette'])], np.float32).copy()
    for i, color in enumerate(colors):
        h,s,v = colorsys.rgb_to_hsv(*map(float,color))
        colors[i] = colorsys.hsv_to_rgb((h+p['hue_shift'])%1, min(1.,s*p['saturation']),v)
    return colors


def pleated_frame(p, size, preset):
    w,h=size;cw,ch=content_size(preset,size);dx,dy=object_offset(preset,size)
    return (w*.5+dx,h*.5+dy),min(cw,ch)*p['size']


def _surface(u, v, p):
    """Nearest visible surface, then bisection; disjoint rows bound memory."""
    dx,dy = p['tilt_x'],p['tilt_y']
    bound = max(.001, max(.35,.34+p['curl'])*p['depth']+.04)
    lo = np.full_like(u,-bound); hi = np.full_like(u,bound)
    found = np.zeros(u.shape,bool)
    step = 2*bound/39
    for z in np.linspace(bound,-bound,40):
        hit = z <= _height(u-dx*z,v-dy*z,p)
        new = hit & ~found
        lo[new] = z; hi[new] = z+step; found |= hit
    for _ in range(5):
        mid = (lo+hi)*.5
        hit = mid <= _height(u-dx*mid,v-dy*mid,p)
        lo = np.where(hit,mid,lo); hi = np.where(hit,hi,mid)
    z = (lo+hi)*.5; u=u-dx*z; v=v-dy*z
    e = .002
    du = (_height(u+e,v,p)-_height(u-e,v,p))/(2*e)
    dv = (_height(u,v+e,p)-_height(u,v-e,p))/(2*e)
    norm = np.sqrt(du*du+dv*dv+1)
    facing = (du*.78 + dv*.28 + .08)/norm
    blend = np.clip((facing+.12)/.92,0,1)**1.5*p['highlight']
    return u,v,z,blend


def _perspective_surface(x, y, p, t):
    """Ray-cast an orbiting camera into the relief, then light its normals.

    Mirrors live in the image plane. Orbit/roll happen after that fold, so a
    single moving sheet produces the changing chevrons, rather than rotating
    an already mirrored flat texture. Distances use artwork units; relief and
    surface travel use cells, keeping density independent of the camera.
    """
    x=x-p['mirror_x'];y=y-p['mirror_y']
    if p['symmetry'] in (1,2): y=np.abs(y)
    if p['symmetry'] in (2,3): x=np.abs(x)
    roll=math.radians(p['angle']);c,s=math.cos(roll),math.sin(roll)
    x,y=x*c-y*s,x*s+y*c
    x=x+p['shear']*y
    ya,pi=math.radians(p['yaw']),math.radians(p['pitch'])
    cy,sy,cp,sp=math.cos(ya),math.sin(ya),math.cos(pi),math.sin(pi)
    # Camera basis: columns of Ry(yaw) Rx(pitch).
    right=(cy,0.,-sy);up=(sy*sp,cp,cy*sp);normal=(sy*cp,-sp,cy*cp)
    distance=p['distance']
    rx=x*right[0]+y*up[0]-distance*normal[0]
    ry=x*right[1]+y*up[1]-distance*normal[1]
    rz=x*right[2]+y*up[2]-distance*normal[2]
    valid=rz < -.015
    rz=np.minimum(rz,-.015)
    density=p['density'];bound=max(.001,max(.35,.34+p['curl'])*p['depth']+.04)
    shift_x=p['pan_x']+t*p['flow']+p['phase'];shift_y=p['pan_y']
    def coords(z):
        along=(z/density-normal[2]*distance)/rz
        a=(normal[0]*distance+along*rx)*density+shift_x
        b=(normal[1]*distance+along*ry)*density+shift_y
        a+=p['irregularity']*.06*np.sin(b*2.1+t*.7)
        b+=p['irregularity']*.035*np.sin(a*2.3-t*.9)
        return a,b
    lo=np.full_like(x,-bound);hi=np.full_like(x,bound);found=np.zeros(x.shape,bool)
    step=2*bound/39
    for z in np.linspace(bound,-bound,40):
        a,b=coords(z);hit=z<=_height(a,b,p);new=hit & ~found
        lo[new]=z;hi[new]=z+step;found|=hit
    for _ in range(5):
        mid=(lo+hi)*.5;a,b=coords(mid);hit=mid<=_height(a,b,p)
        lo=np.where(hit,mid,lo);hi=np.where(hit,hi,mid)
    z=(lo+hi)*.5;a,b=coords(z);e=.002
    du=(_height(a+e,b,p)-_height(a-e,b,p))/(2*e)
    dv=(_height(a,b+e,p)-_height(a,b-e,p))/(2*e)
    norm=np.sqrt(du*du+dv*dv+1)
    light_angle=math.radians(p['light_angle'])
    facing=(du*.83*math.cos(light_angle)+dv*.83*math.sin(light_angle)+.08)/norm
    blend=np.clip((facing+.12)/.92,0,1)**1.5*p['highlight']
    u=(a-shift_x)/density;v=(b-shift_y)/density
    return a,b,z,blend,u,v,valid


def render_pleated_field(arr,p,seconds,preset):
    if not p['mix']: return arr
    h,w=arr.shape[:2];(cx,cy),unit=pleated_frame(p,(w,h),preset)
    cw,ch=content_size(preset,(w,h));artunit=min(cw,ch)
    clock=float(seconds)*preset.get('speed',1.)
    t=math.floor(clock*p['cadence']+1e-8)/p['cadence']
    colors=_palette(p);dark,light,amber,back,back2=colors
    theta=math.radians(p['angle']);cs,sn=math.cos(theta),math.sin(theta)
    result=np.empty_like(arr,dtype=np.float32)
    # Per-tile ray arrays keep memory bounded at export resolutions.
    for top in range(0,h,96):
        y,x=np.mgrid[top:min(h,top+96),:w].astype(np.float32)
        x=(x-cx)/max(1.,unit);y=(y-cy)/max(1.,unit)
        # Film color remains fixed to the canvas, independent of camera zoom.
        bx=(np.arange(w,dtype=np.float32)-w*.5)/max(1.,artunit)
        by=(np.arange(top,min(h,top+96),dtype=np.float32)-h*.5)[:,None]/max(1.,artunit)
        wash=.13+.3*np.sin(bx*3.1+by*2.4+t*.47)+.25*np.cos(bx*4.2-by*3.3-t*.31)
        bg=back+(back2-back)*(np.clip(wash,0,1)*p['background_motion'])[...,None]
        if p.get('projection',0):
            aa,bb,z,blend,u,v,valid=_perspective_surface(x,y,p,t)
        else:
            u=x*cs-y*sn;v=x*sn+y*cs
            if p['symmetry'] in (1,2): v=np.abs(v)
            if p['symmetry'] in (2,3): u=np.abs(u)
            den=np.clip(1+p['perspective']*u,.18,4.)
            a=(u+p['shear']*v)*p['density']/den+p['pan_x']+t*p['flow']+p['phase']
            b=v*p['density']/den+p['pan_y']
            a+=p['irregularity']*.14*np.sin(b*2.1+t*.7)
            b+=p['irregularity']*.06*np.sin(a*2.3-t*.9)
            aa,bb,z,blend=_surface(a,b,p)
            valid=1.
        color=dark+(light-dark)*blend[...,None]
        # Narrow amber valleys give the folds a warm edge, never broad spots.
        valley=np.clip((-z-.15*p['depth'])*8,0,1)*(1-blend)
        color=color*(1-valley[...,None])+amber*valley[...,None]
        sheen=.035*np.sin(aa*1.2+bb*.7+t*.4)+.035*np.sin(bb*7.1-aa*.6)
        color+=sheen[...,None]*np.array((1.,.55,.65),np.float32)
        fold=(aa+p['stagger']*np.sin(math.tau*bb))%1
        seam=np.exp(-((fold-.72)/.042)**2)*np.clip(np.sin(math.tau*bb)*2+.3,0,1)
        color*=1-(p['seams']*seam)[...,None]
        if p.get('projection',0):
            u=x-p['mirror_x'];v=y-p['mirror_y']
        if p['boundary']==1:
            metric=np.hypot(u,v*max(.05,p['taper']))
        elif p['boundary']==2:
            metric=np.maximum(np.abs(u),np.abs(v)*p['taper'])
        else:
            metric=np.abs(u)+np.abs(v)*p['taper']
        if p.get('projection',0) and p['boundary']==0:
            # A moving optical gate gathers the relief horizontally. Unlike
            # shrinking the whole canvas, its rows keep moving through the
            # slit as it closes, leaving intermittent fragments on the axis.
            metric=u+np.abs(v)*p['taper']-p['edge'] if p['symmetry'] in (1,2,3) else metric
            if p['symmetry'] in (2,3): metric=np.abs(u)+np.abs(v)*p['taper']-p['edge']
        elif not p.get('projection',0) and p['symmetry']==1:
            metric=u+np.abs(v)*p['taper']-p['edge']
        # A softly corrugated boundary follows the actual height of the pleats.
        edge=p['aperture']-metric+z*(.45 if p.get('projection',0) else .055)
        alpha=(np.clip(edge*unit+.5,0,1)*valid)[...,None]
        result[top:top+len(y)] = bg*(1-alpha)+color*alpha
    if p['softness']:
        result=np.asarray(Image.fromarray(np.uint8(np.clip(result,0,1)*255)).filter(
            ImageFilter.GaussianBlur(p['softness']*artunit/720)),np.float32)/255
    return np.asarray(arr*(1-p['mix'])+np.clip(result*p['light'],0,1)*p['mix'],np.float32)
