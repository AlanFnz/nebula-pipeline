"""Contact-print film: procedural dye exposure, gate travel and positive/negative ink.

Source pixels supply the printing mask. Timing and wording live in the study,
not in this effect; no reference video or sampled reference images are used.
"""
import colorsys
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def modules(Module, P):
    return (Module('contact_print', 'Contact print',
        'Expose any source through red or colored film, a moving gate and fresh emulsion grain.', (
        P('exposure', 'Exposure', .8, 0, 3, .05),
        P('leak_x', 'Light position X', .4, -1, 2, .01),
        P('leak_y', 'Light position Y', .6, -1, 2, .01),
        P('leak_width', 'Light width', .3, .02, 1.5, .01),
        P('leak_height', 'Light height', 1., .05, 3, .01),
        P('hue', 'Film hue', .985, 0, 1, .01),
        P('light_hue', 'Exposure fringe hue', .88, 0, 1, .01),
        P('edge_dye', 'Edge dye variation', .0, 0, 1, .01),
        P('brightness', 'Film brightness', .92, 0, 1.5, .01),
        P('density', 'Shadow density', 0., 0, 1, .01,
          'Darken unexposed stock while preserving the light leaks.'),
        P('positive', 'Positive impression', 0., 0, 1, .01,
          'Zero prints dark ink; one exposes luminous lettering. Intermediate values cross between polarities.'),
        P('ink_density', 'Ink density', 1., 0, 1, .01),
        P('ink_lift', 'Light through ink', .2, 0, 1, .01),
        P('erosion', 'Impression erosion', .15, 0, 1, .01),
        P('melt', 'Impression distortion', 2., 0, 30, .5,
          'Pixels at a 720-pixel reference edge.'),
        P('softness', 'Optical softness', .7, 0, 6, .1),
        P('halation', 'Positive halation', .4, 0, 1, .01),
        P('opening', 'Gate opening', 1., 0, 1.5, .01),
        P('gate_x', 'Gate center X', .5, -1, 2, .01),
        P('gate_y', 'Gate center Y', .5, -1, 2, .01),
        P('gate_width', 'Gate width', 1., .05, 2, .01),
        P('gate_height', 'Gate height', 1., .05, 2, .01),
        P('gate_angle', 'Gate angle', 0., -180, 180, 1),
        P('gate_softness', 'Gate edge softness', .035, .001, .2, .005),
        P('roughness', 'Gate irregularity', .6, 0, 1, .01),
        P('neighbor', 'Adjacent film strip', 0., 0, 1, .01),
        P('shutter', 'Shutter width', 0., 0, 1.5, .01),
        P('shutter_x', 'Shutter position', .6, -1, 2, .01),
        P('shutter_angle', 'Shutter angle', -15., -180, 180, 1),
        P('scale', 'Impression scale', 1., .1, 4, .01),
        P('x', 'Impression position X', 0., -1, 1, .01),
        P('y', 'Impression position Y', 0., -1, 1, .01),
        P('weave', 'Gate weave', .003, 0, .05, .001),
        P('grain', 'Emulsion grain', .16, 0, .5, .01),
        P('grain_size', 'Grain size', 1., .5, 4, .1),
        P('dust', 'Dust & scratches', .6, 0, 1, .01),
        P('cadence', 'Film cadence', 12., 1, 60, 1),
    )),)


def _field(rng, size, grid):
    return np.asarray(Image.fromarray(rng.random(grid).astype(np.float32)).resize(
        size, Image.Resampling.BICUBIC), np.float32)


def _blur(a, radius):
    if radius <= .01: return a
    return np.asarray(Image.fromarray(np.uint8(np.clip(a, 0, 1)*255)).filter(
        ImageFilter.GaussianBlur(radius)), np.float32)/255


def render_contact_print(arr, p, seconds, speed, seed, reference):
    h,w=arr.shape[:2]; cw,ch=reference; unit=min(cw,ch)/720
    frame=math.floor(max(0.,seconds*speed)*p['cadence']+1e-7)
    rng=np.random.default_rng((int(seed)+frame*104729)%2**32)
    yy,xx=np.mgrid[:h,:w].astype(np.float32)
    x=(xx-w/2)/cw+.5; y=(yy-h/2)/ch+.5
    cloud=_field(rng,(w,h),(7,9)); medium=_field(rng,(w,h),(32,42))
    grain_size=max(.5,p['grain_size']*unit)
    fine=_field(rng,(w,h),(max(2,round(h/grain_size)),max(2,round(w/grain_size))))-.5
    noise=fine*2.6+(medium-.5)*.17
    # The dye stock becomes magenta, then almost white as exposure increases.
    leak=np.exp(-((x-p['leak_x']+.025*np.sin(y*8+frame*.43))/p['leak_width'])**2
                -((y-p['leak_y'])/p['leak_height'])**2)
    exposure=p['exposure']*leak*(.9+.2*cloud)
    red=np.array(colorsys.hsv_to_rgb(p['hue'],1.,p['brightness']),np.float32)
    pink=np.array(colorsys.hsv_to_rgb(p['light_hue'],.98,1.),np.float32)
    white=np.array([1.,.965,.965],np.float32)
    flare=np.clip(exposure+noise*p['grain']*2,0,1)
    bleach=np.clip((exposure-.65)*1.55+noise*p['grain']*2,0,1)
    film=red*(1-flare[...,None])+pink*flare[...,None]
    film=film*(1-bleach[...,None])+white*bleach[...,None]
    dye=np.clip((x-.48)*2,0,1)*p['edge_dye']*(1-bleach)
    violet=np.array(colorsys.hsv_to_rgb((p['light_hue']-.14)%1,.98,.55),np.float32)
    film=film*(1-dye[...,None])+violet*dye[...,None]
    film*= (.91+.13*cloud)[...,None]
    film*= (1-p['density']*(1-np.clip(exposure,0,1)))[...,None]
    # Source resampling is bounded even at oversized scale/translation values.
    dx,dy=rng.normal(0,p['weave'],2)
    sx=p['scale']; tx=(p['x']+dx)*cw; ty=(p['y']+dy)*ch
    source=Image.fromarray(np.uint8(np.max(np.clip(arr,0,1),axis=2)*255))
    source=source.transform((w,h),Image.Transform.AFFINE,
        (1/sx,0,w/2-(w/2+tx)/sx,0,1/sx,h/2-(h/2+ty)/sx),Image.Resampling.BICUBIC)
    ink=np.asarray(source,np.float32)/255
    flow=(medium-.5)*p['melt']*unit*3
    ix=np.clip(np.rint(xx+flow),0,w-1).astype(int)
    iy=np.clip(np.rint(yy+flow*.7),0,h-1).astype(int)
    ink=_blur(ink[iy,ix],p['softness']*unit)
    # Uneven chemical erosion precedes grain. More erosion eats the fine subtitle first.
    if p['erosion']:
        damage=_field(rng,(w,h),(max(2,round(ch/7)),max(2,round(cw/7))))
        ink*=1-p['erosion']*np.clip((.68-damage)*5,0,1)
    dark=np.array([.012,0.,.006],np.float32)+p['ink_lift']*np.clip(exposure,0,1)[...,None]*np.array([.68,.015,.19],np.float32)
    positive=pink*(1-np.clip(exposure+.6,0,1)[...,None])+white*np.clip(exposure+.6,0,1)[...,None]
    pigment=dark*(1-p['positive'])+positive*p['positive']
    film=film*(1-ink[...,None]*p['ink_density'])+pigment*ink[...,None]*p['ink_density']
    halo=np.maximum(0.,_blur(ink,8*unit)-ink)*p['halation']*p['positive']
    film+=halo[...,None]*pink*1.5
    film+=noise[...,None]*p['grain']*(.08+.55*(1-bleach[...,None]))*np.clip(film+.1,0,1)
    # Visible defects stay attached to the moving piece of film for this frame.
    dirt=Image.new('L',(w,h)); draw=ImageDraw.Draw(dirt)
    for _ in range(round(p['dust']*65)):
        cx,cy=rng.uniform(0,w),rng.uniform(0,h)
        rw=rng.uniform(.5,6.2)*unit; rh=rw*rng.uniform(1,3)
        vertices=[]
        for theta in np.linspace(0,math.tau,9,endpoint=False):
            radius=rng.uniform(.65,1.25)
            vertices.append((cx+math.cos(theta)*rw*radius,cy+math.sin(theta)*rh*radius))
        draw.polygon(vertices,fill=int(rng.uniform(100,255)))
    dirt=_blur(np.asarray(dirt,np.float32)/255,1.*unit)
    film*=1-dirt[...,None]*.85
    for _ in range(round(p['dust']*8)):
        sx0=rng.uniform(0,w); sy0=rng.uniform(0,h); length=rng.uniform(3,38)*unit
        scratch=np.exp(-((xx-sx0)/(max(.45,unit*.6)))**2)*np.clip(1-abs(yy-sy0)/max(1.,length),0,1)
        film+=scratch[...,None]*np.array([.45,.27,.35],np.float32)
    # Superellipse gate has broad flat edges and gently rounded corners.
    angle=math.radians(p['gate_angle']); c,s=math.cos(angle),math.sin(angle)
    gx=(x-p['gate_x']-dx)*c+(y-p['gate_y']-dy)*s
    gy=-(x-p['gate_x']-dx)*s+(y-p['gate_y']-dy)*c
    gw=max(.0001,p['opening']*p['gate_width']*.49)
    gh=max(.0001,p['gate_height']*.49)
    distance=((abs(gx)/gw)**8+(abs(gy)/gh)**8)**.125
    distance+=(cloud-.5)*p['roughness']*.12+noise*p['grain']*.17
    edge=max(.002,p['gate_softness']*3)
    gate=np.clip((1-distance)/edge+.5,0,1)
    gate=gate*gate*(3-2*gate)
    if p['opening']<=0: gate*=0
    film*=gate[...,None]
    if p['neighbor']:
        strip=(np.clip((gx-gw-.045)/.01,0,1)*np.clip((gw+.17-gx)/.02,0,1)
               *np.clip((.48-abs(gy))/.04,0,1))
        film=np.maximum(film,strip[...,None]*red*(.8+.2*noise[...,None])*p['neighbor'])
    if p['shutter']:
        a=math.radians(p['shutter_angle'])
        projected=(x-p['shutter_x'])*math.cos(a)+(y-.5)*math.sin(a)
        cover=np.clip((p['shutter']/2-abs(projected))/.01,0,1)
        film*=1-cover[...,None]
    return np.clip(film,0,1).astype(np.float32)
