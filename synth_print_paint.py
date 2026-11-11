"""Opt-in painted-color surface for the existing Print surface effect.

Screen-space pigment, paper and drawing move independently at the scan cadence.
Works with any source; no sculpture masks, reference images or frame history.
"""
import math
import numpy as np
from PIL import Image, ImageFilter
from synth_print import _rng, _paper_noise, _fresh_noise


PAINT_KEYS = frozenset(('paint_flatten', 'paint_tones', 'paint_wash', 'paint_drift',
    'paint_registration', 'paint_outline', 'paint_outline_width', 'paint_rim', 'paint_period'))
PAINT_SHARED = frozenset(('surface', 'cadence', 'ink_grain', 'ink_wear', 'grain_size',
    'boil', 'paper_motion', 'registration', 'rotation_jitter', 'softness', 'mix', 'effect_intensity'))


def applicable_paths(paths, mode):
    if mode == (0, 0): return tuple(p for p in paths if p.split('.')[-1] not in PAINT_KEYS)
    if mode == (1, 1): return tuple(p for p in paths if p.split('.')[-1] in PAINT_KEYS | PAINT_SHARED)
    return tuple(paths)


def _blur(a, radius):
    return np.asarray(Image.fromarray(np.uint8(np.clip(a, 0, 1)*255)).filter(
        ImageFilter.GaussianBlur(max(0., radius))), np.float32)/255.


def _sample(a, x, y):
    h,w=a.shape[:2]
    x=np.clip(x,0,w-1);y=np.clip(y,0,h-1)
    ix=x.astype(np.int32);iy=y.astype(np.int32)
    fx=(x-ix.astype(np.float32))[...,None];fy=(y-iy.astype(np.float32))[...,None]
    jx=np.minimum(ix+1,w-1);jy=np.minimum(iy+1,h-1)
    return (a[iy,ix]*(1-fx)+a[iy,jx]*fx)*(1-fy)+(a[jy,ix]*(1-fx)+a[jy,jx]*fx)*fy


def paint_tick(time, speed, cadence, period):
    t=time*speed
    if period > 0:
        phase=round((t/period)%1.,10)%1.
        return math.floor(phase*max(1,round(period*cadence))+1e-8)
    return math.floor(t*cadence+1e-8)


def render_painted_surface(arr, p, time, speed, seed):
    h,w=arr.shape[:2];unit=min(w,h)/720.
    tick=paint_tick(time,speed,p['cadence'],p['paint_period'])
    rng=_rng(seed,311,tick)
    # Reuse Print surface's paper tooth, held random clock and noise utilities.
    size=max(.65,p['grain_size']*unit)
    fixed=_paper_noise(seed,w,h,size,0)
    sx,sy=np.rint(rng.uniform(-1,1,2)*p['paper_motion']*min(w,h)).astype(int)
    fixed=(np.roll(fixed,(sy,sx),(0,1))-.5)*3.5
    tooth=_fresh_noise(rng,w,h,size,size)
    grain=fixed*(1-p['boil'])+tooth*p['boil']
    wash=_fresh_noise(rng,w,h,max(3,unit*42),max(3,unit*60))
    brush=_fresh_noise(rng,w,h,max(2,unit*3),max(2,unit*8))
    flow_y=_fresh_noise(rng,w,h,max(3,unit*50),max(3,unit*38))
    y,x=np.mgrid[:h,:w].astype(np.float32)
    dx,dy,angle=rng.uniform(-1,1,3)
    angle*=math.radians(p['rotation_jitter'])
    cx=x-w/2;cy=y-h/2
    x=cx*math.cos(angle)+cy*math.sin(angle)+w/2+dx*p['registration']*min(w,h)
    y=-cx*math.sin(angle)+cy*math.cos(angle)+h/2+dy*p['registration']*min(w,h)
    x+=(wash*.6+brush*.28)*p['paint_drift']*unit
    y+=(flow_y*.6-brush*.21)*p['paint_drift']*unit
    line_source=_blur(arr,max(.3,unit*.7))
    color=_sample(line_source,x+dx*p['paint_registration']*unit,
                  y+dy*p['paint_registration']*unit)
    # Soft tone terraces replace a perfectly smooth 3D gradient. Fine pigment
    # varies their coverage; it never cuts large black holes into the source.
    value=np.max(color,axis=2)
    lift=np.clip((value-.45)/.5,0,1)
    lifted=np.clip(value+.16*lift*lift*(3-2*lift),0,1)
    count=p['paint_tones']
    tones=lifted*count+wash*.13
    lower=np.floor(tones);fraction=tones-lower
    terrace=(lower+fraction*fraction*(3-2*fraction))/count
    target=value*(1-p['paint_flatten'])+terrace*p['paint_flatten']
    color*=np.clip(target/np.maximum(value,.015),0,1.8)[...,None]
    color*=1+(wash*.085+brush*.03)[...,None]*p['paint_wash']
    # Drawing is sampled independently from the pigment; color boundaries also
    # count, so equally bright red and blue retain their drawn separation.
    radius=max(1,round(p['paint_outline_width']*unit))
    padx=np.pad(line_source,((radius,radius),(radius,radius),(0,0)),mode='edge')
    delta_x=np.linalg.norm(padx[radius:h+radius,2*radius:]-padx[radius:h+radius,:w],axis=2)
    delta_y=np.linalg.norm(padx[2*radius:,radius:w+radius]-padx[:h,radius:w+radius],axis=2)
    drawing=np.clip((np.maximum(delta_x,delta_y)-.08)*2.4,0,1)[...,None]
    contour=_sample(drawing,x,y)[...,0]
    broken=np.clip(.8+brush*.18+grain*.09,.25,1.)
    rim=_sample(drawing,x-dx*p['paint_registration']*unit,y-dy*p['paint_registration']*unit)[...,0]
    paper=np.array((.89,.86,.73),np.float32)
    rim*=p['paint_rim']*broken*.7
    color=color*(1-rim[...,None])+paper*rim[...,None]
    color*=1-(contour*p['paint_outline']*broken*.8)[...,None]
    # Dense fine stipple in shaded pigment, with weaker speckling on flat paint.
    shadow=1-np.max(color,axis=2)
    density=np.clip(.6+wash*.25,.15,1.1)
    pigment=grain*p['ink_grain']*(.025+.095*shadow)*(.7+.3*density)
    pores=np.maximum(tooth-.4,0)*p['ink_wear']*(.055+.08*shadow)*density
    color+=pigment[...,None];color-=pores[...,None]
    if p['softness']:color=_blur(color,p['softness']*unit)
    color+=(rng.random((h,w,1),dtype=np.float32)-.5)*p['ink_grain']*.025
    return arr*(1-p['mix'])+np.clip(color,0,1)*p['mix']
