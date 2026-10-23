"""Optical print collage and film exposure, sampled without temporal state.

No reference image or study choreography is embedded here. Bright input is ink
in color-print mode; zero color-print amount keeps the incoming photograph.
"""
import colorsys
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def modules(Module, P):
    return (
        Module('print_collage', 'Print collage', 'Crop, enlarge and overprint impressions of any image source.', (
            P('reading_layout', 'Follow reading montage', 0., 0, 1, .05, 'With Text → Show → Reading montage, keep complete centered words while reading and overprints during interruptions. Zero retains manual collage controls. Other sources are unchanged.'),
            P('start', 'Source window start', 0., 0, .99, .01, 'Horizontal position within the non-black source bounds.'),
            P('end', 'Source window end', 1., .01, 1, .01, 'Reversed or very narrow windows keep at least one source pixel.'),
            P('width', 'Impression width', .9, .02, 4, .01, 'Relative to the authored canvas width. Values above one crop at the canvas edge.'),
            P('height', 'Height stretch', 1., .1, 5, .01),
            P('x', 'Position X', 0., -1, 1, .01),
            P('y', 'Position Y', 0., -1, 1, .01),
            P('copies', 'Impressions', 1, 1, 6, 1),
            P('gap', 'Impression spacing', .1, 0, 1, .01),
            P('poster', 'Large overprint', 0., 0, 1, .01),
            P('poster_scale', 'Overprint scale', 2.5, .1, 8, .1),
            P('poster_start', 'Overprint window start', 0., 0, .99, .01),
            P('poster_end', 'Overprint window end', 1., .01, 1, .01),
            P('poster_y', 'Overprint offset Y', .08, -.8, .8, .01),
            P('echo', 'Small overprint', 0., 0, 1, .01),
            P('echo_x', 'Small overprint X', .3, -1, 1, .01),
            P('echo_y', 'Small overprint Y', .22, -1, 1, .01),
            P('bars', 'Diagonal bars', 0., 0, 1, .01),
            P('bar_angle', 'Bar angle', -35., -180, 180, 1),
            P('bar_count', 'Bar count', 6, 1, 16, 1),
            P('weave', 'Gate weave', .003, 0, .05, .001),
            P('cadence', 'Print cadence', 12., 1, 60, 1),
        )),
        Module('film_burn', 'Film burn', 'Drifting light leaks, ink reversals and rough film gates. Color print remaps bright source details into ink.', (
            P('reading_clarity', 'Reading clarity', 0., 0, 1, .05, 'With Text → Show → Reading montage, soften occlusion during reading and intensify exposure during interruptions. Grain and palette remain. Zero retains the manual exposure.'),
            P('print_mix', 'Color print', 0., 0, 1, .01, 'One turns bright details into ink on colored film. Zero preserves the source colors.'),
            P('paper_hue', 'Film hue', .98, 0, 1, .01),
            P('paper_light', 'Film brightness', .85, 0, 1.5, .01),
            P('ink_hue', 'Ink hue', .44, 0, 1, .01),
            P('ink_light', 'Ink brightness', .12, 0, 1, .01),
            P('color_spread', 'Color variation', .65, 0, 1, .01),
            P('exposure', 'Light leak strength', .8, 0, 2, .01),
            P('leak_x', 'Light leak position', .45, -1, 2, .01),
            P('leak_y', 'Light leak height position', .5, -1, 2, .01),
            P('leak_height', 'Light leak height', 2., .05, 3, .01),
            P('damage', 'Emulsion damage', 0., 0, 1, .01, 'Colored flecks and uneven pigment near the exposure.'),
            P('leak_hue', 'Light leak hue', .12, 0, 1, .01, 'Amber, rose or another tint around the pale center.'),
            P('leak_width', 'Light leak width', .18, .01, 1, .01),
            P('drift', 'Light leak drift', .2, 0, 1, .01),
            P('rate', 'Film movement', .8, 0, 4, .01),
            P('reversal', 'Ink reversal', .8, 0, 1.5, .01, 'Exposed areas turn from dark ink into luminous positive lettering.'),
            P('halo', 'Luminous edges', .8, 0, 2, .01),
            P('halo_width', 'Edge glow width', 7., 0, 25, .5, 'Pixels at a 720-pixel reference edge.'),
            P('ink_spread', 'Ink spread', 0., 0, 10, .5, 'Soften corners and thicken bright source details before printing.'),
            P('melt', 'Emulsion distortion', 2.5, 0, 25, .5, 'Local bending of the image, strongest inside the exposure.'),
            P('opening', 'Gate opening', 1.3, 0, 2, .01, 'Zero closes the gate; values above one reveal the full canvas.'),
            P('gate_x', 'Gate center', .48, -1, 2, .01),
            P('roughness', 'Gate irregularity', .7, 0, 1, .01),
            P('softness', 'Optical softness', .6, 0, 5, .1),
            P('grain', 'Film grain', .075, 0, .3, .005),
            P('dust', 'Dust & scratches', .35, 0, 1, .01),
            P('cadence', 'Film cadence', 12., 1, 60, 1),
        )),
    )


def _blur(a, radius):
    if radius <= .01: return a
    im = Image.fromarray(np.uint8(np.clip(a, 0, 1) * 255))
    return np.asarray(im.filter(ImageFilter.GaussianBlur(radius)), np.float32) / 255


def _field(rng, shape, grid):
    h, w = shape
    im = Image.fromarray(rng.random(grid).astype(np.float32), 'F')
    return np.asarray(im.resize((w, h), Image.Resampling.BICUBIC), np.float32)


def _clock(seconds, speed, cadence, seed):
    frame = math.floor(seconds * speed * cadence + 1e-7)
    return frame / cadence, np.random.default_rng((int(seed) + frame * 104729) % (2**32))


def render_print_collage(arr, p, seconds, speed, seed, reference, reading=None):
    if reading is not None:
        from synth_reading_montage import collage_reading_params
        p = collage_reading_params(p, reading)
    h, w = arr.shape[:2]
    cw, ch = reference
    _, rng = _clock(seconds, speed, p['cadence'], seed)
    original = Image.fromarray(np.uint8(np.clip(arr, 0, 1)*255), 'RGB')
    ink = np.max(arr, axis=2) > .08
    rows, cols = np.nonzero(ink)
    if not len(cols): return arr.copy()
    left, right, top, bottom = int(cols.min()), int(cols.max()+1), int(rows.min()), int(rows.max()+1)
    extent = right-left
    start = left + min(extent-1, int(p['start']*extent))
    end = max(start+1, min(right, left+int(p['end']*extent)))
    sample = original.crop((start, top, end, bottom))
    dx, dy = rng.normal(0, p['weave'], 2) * min(cw, ch)
    cx, cy = w/2 + p['x']*cw + dx, h/2+p['y']*ch+dy
    def stamp(width, x, y, opacity=1., height_scale=1., sample=sample):
        # Render by inverse transform: no giant intermediate for oversized crops.
        scale_x = max(.001, width/sample.width)
        scale_y = scale_x * height_scale
        transformed = sample.transform((w, h), Image.Transform.AFFINE,
            (1/scale_x, 0, sample.width/2-x/scale_x,
             0, 1/scale_y, sample.height/2-y/scale_y), Image.Resampling.BILINEAR)
        return np.asarray(transformed, np.float32)/255*opacity
    width = cw*p['width']
    if reading is not None and not reading.burst:
        amount = p.get('reading_layout', 0.)
        fitted = min(width, sample.width, cw*.92, ch*.52*sample.width/max(1, sample.height)/p['height'])
        width += (fitted-width)*amount
    result = np.zeros((h,w,3),np.float32)
    if p['poster']:
        a=left+min(extent-1,int(p['poster_start']*extent))
        b=max(a+1,min(right,left+int(p['poster_end']*extent)))
        poster=original.crop((a,top,b,bottom))
        result = stamp(width*p['poster_scale'],cx,cy+p['poster_y']*ch,p['poster'],p['height'],poster)
    count = int(p['copies'])
    for i in range(count):
        result = np.maximum(result, stamp(width, cx+(i-(count-1)/2)*(width+p['gap']*cw),cy,1.,p['height']))
    if p['echo']:
        result = np.maximum(result,stamp(width*.32,cx+p['echo_x']*cw,cy+p['echo_y']*ch,p['echo']))
    if p['bars']:
        bars = Image.new('L',(w,h)); draw=ImageDraw.Draw(bars)
        angle=math.radians(p['bar_angle']); u=np.array([math.cos(angle),math.sin(angle)])
        v=np.array([-u[1],u[0]])
        for i in range(int(p['bar_count'])):
            center=np.array([w*.5,h*.64])+u*(i-(p['bar_count']-1)/2)*cw*.075
            pts=[tuple(center+u*a*cw+v*b*ch) for a,b in ((-.025,-.06),(.025,-.06),(.025,.06),(-.025,.06))]
            draw.polygon(pts,fill=255)
        result=np.maximum(result,np.asarray(bars,np.float32)[...,None]/255*p['bars'])
    return result


def render_film_burn(arr, p, seconds, speed, seed, reference):
    h,w=arr.shape[:2]; cw,ch=reference; unit=min(cw,ch)/720
    t,rng=_clock(seconds,speed,p['cadence'],seed)
    t*=p['rate']
    y,x=np.mgrid[:h,:w].astype(np.float32)
    x=(x-w/2)/cw+.5; y=(y-h/2)/ch+.5
    cloud=_field(rng,(h,w),(7,8))
    small_cloud=_field(rng,(h,w),(38,50))
    fine=rng.normal(0,1,(h,w)).astype(np.float32)
    center=p['leak_x']+p['drift']*(.65*math.sin(t*1.9)+.35*math.sin(t*3.13+1))
    crooked=.024*np.sin(y*7+t*2)+.015*np.sin(y*17-t*1.6)
    leak=np.exp(-((x-center+crooked)/p['leak_width'])**2)
    leak*=np.exp(-((y-p['leak_y'])/p['leak_height'])**2)
    leak*=p['exposure']*(.94+.12*cloud)
    # Small nonperiodic changes complement broad continuous optical motion.
    leak+=p['exposure']*.12*cloud
    image=arr
    if p['melt']:
        xx,yy=np.meshgrid(np.arange(w),np.arange(h))
        flow=((cloud-.5)+(small_cloud-.5)*.7)*p['melt']*unit*(1+leak*2)
        xx=np.clip(np.rint(xx+flow+np.sin(yy*.035/max(unit,.1)+t)*p['melt']*unit*.25),0,w-1).astype(int)
        yy=np.clip(np.rint(yy+flow*.6),0,h-1).astype(int)
        image=image[yy,xx]
    ink=np.max(image,axis=2)
    if p['ink_spread']:
        ink=np.clip((_blur(ink,p['ink_spread']*unit)-.23)*3.3,0,1)
    ink=_blur(ink,p['softness']*unit)
    hue=p['paper_hue']
    red=np.array(colorsys.hsv_to_rgb(hue, .99, p['paper_light']),np.float32)
    magenta=np.array(colorsys.hsv_to_rgb((hue-.1)%1,.97,p['paper_light']*.65),np.float32)
    wash=np.clip(.35+.35*np.sin(x*5-y*1.8+t*.3)+.45*(cloud-.5),0,1)*p['color_spread']
    paper=red*(1-wash[...,None])+magenta*wash[...,None]
    paper*= (.8+.27*cloud)[...,None]
    warm=np.array(colorsys.hsv_to_rgb(p['leak_hue'],.75,1.),np.float32)
    white=np.array([1.,.96,.82],np.float32)
    # The leak crosses red, amber, cream and finally clipped white stock.
    warm_mix=np.clip(leak*.65,0,1)[...,None]
    paper=paper*(1-warm_mix)+warm*warm_mix
    hot=np.clip((leak-.85)*1.15,0,1)[...,None]
    paper=paper*(1-hot)+white*hot
    dark=np.array(colorsys.hsv_to_rgb(p['ink_hue'],.56,p['ink_light']),np.float32)
    pigment=dark*(.75+.5*cloud[...,None])
    pigment= pigment*(1-p['color_spread']*.2*x[...,None])+np.array([.26,.15,.08],np.float32)*p['color_spread']*.2*x[...,None]
    positive=np.clip(p['reversal']-leak*.8,0,1)
    positive=np.maximum(positive,np.clip((leak-.4)*1.1,0,1)*(1-min(1.,p['reversal'])))
    pigment=pigment*(1-positive[...,None])+white*positive[...,None]
    if p['damage']:
        broken=np.clip((small_cloud-.61)*7,0,1)*p['damage']*np.clip(leak,0,1)*ink
        pigment=pigment*(1-broken[...,None])+np.array([.015,.38,.25],np.float32)*broken[...,None]
    # Partial reversal retains the red stock in the cores of exposed ink.
    solar=np.clip(leak*.6,0,.85)*min(1.,p['reversal'])
    pigment=pigment*(1-solar[...,None])+paper*solar[...,None]
    printed=paper*(1-ink[...,None])+pigment*ink[...,None]
    photographic=np.clip(image+leak[...,None]*warm,0,1)
    result=photographic*(1-p['print_mix'])+printed*p['print_mix']
    glow_radius=max(.15,p['halo_width']*unit)
    blurred=_blur(ink,glow_radius)
    tight=_blur(ink,max(.3,glow_radius*.21))
    edge=np.clip(blurred-ink,0,1)
    # Detect transitions, rather than treating every midtone as an edge.
    gx=np.diff(tight,axis=1,append=tight[:,-1:])
    gy=np.diff(tight,axis=0,append=tight[-1:,:])
    rim=np.clip(np.hypot(gx,gy)*max(1.,unit*5.),0,1)
    halo_strength=p['halo']*(.65+leak*.65)
    result+=edge[...,None]*halo_strength[...,None]*np.array([.9,.45,.55],np.float32)*2.4
    result+=rim[...,None]*halo_strength[...,None]*white*.3
    result=_blur(result,max(.2,p['softness']*unit))
    # Fine emulsion grain also remains visible inside the lettering.
    result+=fine[...,None]*p['grain']*(.3+.6*np.clip(result,0,1))
    result+=(rng.random((h,w,3),dtype=np.float32)-.5)*p['grain']*.5
    if p['dust']:
        specks=Image.new('L',(w,h));d=ImageDraw.Draw(specks)
        for _ in range(int(p['dust']*65)):
            px,py=rng.uniform(0,w),rng.uniform(0,h)
            radius=max(.4,unit*rng.uniform(.6,3.2))
            d.ellipse((px,py,px+radius,py+radius*rng.uniform(.8,3)),fill=int(rng.uniform(80,240)))
        if rng.random()<p['dust']*.65:
            sx=rng.uniform(0,w);sy=rng.uniform(0,h)
            d.line((sx,sy,sx+unit*rng.uniform(-8,8),sy+unit*rng.uniform(15,90)),fill=110,width=max(1,round(unit)))
        mask=np.asarray(specks,np.float32)/255
        result*=1-mask[...,None]
    # Gate loss is a rough optical aperture, not a geometric rectangular crop.
    gate_noise=((cloud-.5)*.08+(small_cloud-.5)*.055+fine*.009)*p['roughness']
    left=p['gate_x']-p['opening']/2+.015*p['roughness']*np.sin(y*18+t*2)
    right=p['gate_x']+p['opening']/2+.018*p['roughness']*np.sin(y*11-t*1.8)
    distance=np.minimum(x-left,right-x)+gate_noise
    gate=np.clip(distance/.018,0,1)
    gate=gate*gate*(3-2*gate)
    if p['opening']<=0: gate=np.zeros_like(gate)
    return np.clip(result,0,1).astype(np.float32)*gate[...,None]
