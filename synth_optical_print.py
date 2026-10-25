"""Layered optical printing of any source, with optional semantic reading holds.

All cuts, texture and registration are sampled from absolute time. Source pixels
are used as exposure masks; no reference frames or fixed wording are embedded.
"""
import colorsys
import math

import numpy as np
from PIL import Image, ImageFilter


def modules(Module, P):
    return (Module('optical_print', 'Optical overprint',
        'Dark stock, enlarged exposures and distressed colored impressions.', (
        P('reading_clarity', 'Protect reading moments', 0., 0, 1, .05,
          'With Text → Reading montage, keep whole words in frame and move flashes away while reading. Other sources use the manual composition.'),
        P('reading_hold', 'Readable hold', .7, .25, 1, .05,
          'Fraction of each word hold kept clear before optical excursions. One protects the full hold. The final phrase stays protected throughout.'),
        P('primary', 'Main impression', 1., 0, 1, .01),
        P('width', 'Impression width', .86, .1, 1.5, .01),
        P('position_x', 'Position X', 0., -.5, .5, .01),
        P('position_y', 'Position Y', 0., -.5, .5, .01),
        P('enlargement', 'Large impression scale', 3.8, 1, 8, .1),
        P('overprint', 'Large impression strength', .7, 0, 1, .01),
        P('fragment_mix', 'Fragment montage', 0., 0, 1, .05,
          'Replace the repeated background with varied closeups, dark exposures and a second ink impression. The main word keeps its size, timing and focus. Zero retains the original background.'),
        P('fragment_typeface', 'Fragment typeface', 0, 0, 2, 1,
          'Optional alternate typeface for background fragments in Reading montage. The main text stays unchanged. Other sources use their own pixels.',
          choices=('Source pixels', 'Bodoni / serif', 'Fraunces / soft serif'), kind='font'),
        P('halation', 'Exposure halation', 0., 0, 1, .05,
          'Red light diffusion around secondary exposures and a brighter pale flash core. Does not blur the main word.'),
        P('registration', 'Registration drift', .035, 0, .2, .005),
        P('red_hue', 'First ink hue', .99, 0, 1, .01),
        P('second_hue', 'Second ink hue', .72, 0, 1, .01),
        P('light_hue', 'Pale ink hue', .12, 0, 1, .01),
        P('brightness', 'Ink brightness', .95, .1, 1.5, .01),
        P('pale_ink', 'Pale ink patches', .55, 0, 1, .01),
        P('stock', 'Stock brightness', .008, 0, .2, .005),
        P('cuts', 'Cut rate', 3., 0, 12, .1,
          'Unequal optical exposures per second, on average. Zero freezes the exposure layout; grain follows Print cadence.'),
        P('motion', 'Optical movement', .7, 0, 1, .01),
        P('focus', 'Focus breathing', .6, 0, 1, .01),
        P('softness', 'Print softness', 2.4, 0, 6, .1),
        P('damage', 'Pigment erosion', .45, 0, 1, .01),
        P('grain', 'Film grain', .065, 0, .25, .005),
        P('dust', 'Dust & scratches', .4, 0, 1, .01),
        P('stripes', 'Diagonal exposure', .6, 0, 1, .01),
        P('stripe_angle', 'Exposure angle', -35., -180, 180, 1),
        P('spot', 'Exposure flashes', .85, 0, 1, .01),
        P('spot_size', 'Flash size', .14, .025, .4, .005,
          'Diameter relative to the shorter canvas edge.'),
        P('cadence', 'Print cadence', 12., 1, 60, 1),
    )),)


def _rng(seed, index):
    return np.random.default_rng((int(seed) + int(index) * 104729) % 2**32)


def _blur(a, radius):
    if radius <= .01: return a
    return np.asarray(Image.fromarray(np.uint8(np.clip(a, 0, 1)*255)).filter(
        ImageFilter.GaussianBlur(float(radius))), np.float32)/255


def _field(rng, size, grid):
    return np.asarray(Image.fromarray(rng.random(grid).astype(np.float32), 'F').resize(
        size, Image.Resampling.BICUBIC), np.float32)


def exposure_at(t, rate, seed):
    """Random-duration cuts in bounded blocks; seeks never replay prior frames."""
    if rate <= 0: return 0, 0.
    clock = max(0., t) * rate / 4
    block = math.floor(clock)
    spans = _rng(seed, block+8191).uniform(.35, 1.9, 4)
    ends = np.cumsum(spans / spans.sum())
    u = clock - block
    index = min(3, int(np.searchsorted(ends, u, side='right')))
    start = 0. if index == 0 else ends[index-1]
    return block*4+index, float((u-start)/(ends[index]-start))


def render_optical_print(arr, p, seconds, speed, seed, reference, reading=None):
    h, w = arr.shape[:2]; cw, ch = reference
    unit = min(cw, ch)/720
    frame = math.floor(max(0., seconds*speed)*p['cadence']+1e-7)
    t = frame/p['cadence']
    cut, progress = exposure_at(t, p['cuts'], seed)
    layout = _rng(seed+3, cut)
    texture = _rng(seed+71, frame)
    # Large pigment islands stay attached to each impression. Fine grain moves.
    pigment_rng = _rng(seed+109, cut)
    cloud = .7*_field(pigment_rng, (w,h), (6,8)) + .3*_field(pigment_rng, (w,h), (27,35))
    chips = _field(pigment_rng, (w,h), (max(4,round(ch/4)), max(4,round(cw/4))))
    fine = texture.normal(0,1,(h,w)).astype(np.float32)
    protection = p['reading_clarity'] * (1-min(1., reading.burst)) if reading else 0.
    final_hold = bool(reading and reading.final and not reading.burst)
    if reading and not reading.final and p['reading_hold']<1:
        tail=np.clip((reading.progress-p['reading_hold'])/.12,0,1)
        protection*=1-tail*tail*(3-2*tail)
    mode = int(layout.integers(0,5))
    red = np.array(colorsys.hsv_to_rgb(p['red_hue'], .99, p['brightness']),np.float32)
    purple = np.array(colorsys.hsv_to_rgb(p['second_hue'], .84, p['brightness']*.88),np.float32)
    cream = np.array(colorsys.hsv_to_rgb(p['light_hue'], .16, 1.),np.float32)
    yy,xx = np.mgrid[:h,:w].astype(np.float32)
    nx=(xx-w/2)/cw; ny=(yy-h/2)/ch
    stock = np.full((h,w,3),p['stock'],np.float32)
    source = np.max(np.clip(arr,0,1),axis=2)
    rows, cols = np.nonzero(source>.06)
    main = np.zeros_like(source); giant=main.copy(); bounds=None
    if len(cols):
        left,right=int(cols.min()),int(cols.max()+1)
        top,bottom=int(rows.min()),int(rows.max()+1)
        sample=Image.fromarray(np.uint8(source[top:bottom,left:right]*255))
        def stamp(width,x,y):
            scale=max(.001,width/sample.width)
            return np.asarray(sample.transform((w,h),Image.Transform.AFFINE,
                (1/scale,0,sample.width/2-x/scale,0,1/scale,sample.height/2-y/scale),
                Image.Resampling.BILINEAR),np.float32)/255
        smooth=progress*progress*(3-2*progress)
        travel=(smooth-.5)*p['motion']
        dx,dy=layout.uniform(-1,1,2)
        width=cw*p['width']
        fitted=min(width,cw*.9,ch*.58*sample.width/sample.height)
        width=width*(1-protection)+fitted*protection
        # Long words retain their full width. Short ones can breathe vertically.
        excursion=layout.uniform(.65,2.6)
        main_scale=(1+travel*.3*(1-protection))*(1+p['motion']*(1-protection)*(excursion-1))
        # Different print sizes and registrations cut against a readable hold,
        # rather than keeping one centered caption over a moving backdrop.
        if protection and not final_hold:
            main_scale*=1-protection*p['motion']*layout.uniform(.0,.24)
        mx=w/2+p['position_x']*cw+dx*p['registration']*cw*(1-protection*.8)
        my=h/2+p['position_y']*ch+dy*p['registration']*ch*(1-protection*.8)
        mx+=dx*cw*.3*p['motion']*(1-protection)
        my+=dy*ch*.2*p['motion']*(1-protection)
        if not final_hold:
            my+=dy*ch*.13*p['motion']*protection
            mx+=dx*cw*.035*p['motion']*protection
        main=stamp(width*main_scale,mx,my)
        half_w=width*main_scale/2; half_h=half_w*sample.height/sample.width
        bounds=(mx-half_w,mx+half_w,my-half_h,my+half_h)
        gx=w/2+layout.uniform(-.75,.75)*cw+travel*cw*.35
        gy=h/2+layout.uniform(-.55,.55)*ch-travel*ch*.2
        giant=stamp(max(width,cw*.65)*p['enlargement'],gx,gy)
        giant=_blur(giant,(5+layout.uniform(0,17)*p['focus'])*unit)
    angle=math.radians(p['stripe_angle'])
    stripe=(np.sin((nx*math.cos(angle)+ny*math.sin(angle))*25+cut*.71)>.2).astype(np.float32)
    stripe=_blur(stripe,3*unit)*p['stripes']*(.5 if mode==0 else .07)
    background=np.maximum(giant*p['overprint'],stripe)
    background*=1-protection*.45
    stock+=red[None,None,:]*background[...,None]*(.7+.3*cloud[...,None])
    if p.get('fragment_mix',0.):
        from synth_optical_layers import secondary_exposures
        layered=secondary_exposures(source,p,cut,progress,seed,reference,reading,
                                    protection,red,purple,cream)
        if protection and bounds:
            left,right,top,bottom=bounds
            clear=((xx>=left-8*unit)&(xx<=right+8*unit)&
                   (yy>=top-8*unit)&(yy<=bottom+8*unit)).astype(np.float32)
            layered*=1-_blur(clear,24*unit)[...,None]*protection*.72
        stock=stock*(1-p['fragment_mix'])+layered*p['fragment_mix']
    # An irregular registration rim and chipped cream pigment mimic two passes
    # through a printer. The center remains legible during protected holds.
    rim=_blur(main,2.5*unit)
    blurred=_blur(main,(p['softness']+(1-protection)*p['focus']*(9 if mode==1 else 2))*unit)
    erosion=np.clip((chips-.74)*8,0,1)*p['damage']*(1-protection*.65)
    ink=blurred*(1-erosion)
    pale=np.clip((cloud*.65+chips*.35-.5)*6,0,1)*p['pale_ink']
    if mode in (0,1,3): pale*=.14
    color=red if mode in (0,1,3) else purple
    if reading and reading.final: color=purple
    colored=color[None,None,:]*(1-pale[...,None])+cream*pale[...,None]
    # Dark halo gives separation only around glyphs, without a label rectangle.
    stock*=1-_blur(main,7*unit)[...,None]*protection*.65
    stock+=purple[None,None,:]*np.maximum(0,rim-main)[...,None]*.65
    stock=stock*(1-ink[...,None]*p['primary'])+colored*ink[...,None]*p['primary']
    if p['spot'] and layout.random()<.65:
        sx,sy=layout.uniform(-.42,.42,2)
        radius=p['spot_size']*min(cw,ch)/2
        spot_strength=p['spot']
        if protection and bounds:
            # Try clear margins around the entire word, including its spaces.
            # If no full circle fits, omit this flash instead of obscuring type.
            left,right,top,bottom=bounds
            candidates=[(sx,-.4),(sx,.4),(-.42,-.4),(.42,.4),(-.42,.4),(.42,-.4)]
            for sx,sy in candidates:
                px,py=w/2+sx*cw,h/2+sy*ch
                if px+radius<left or px-radius>right or py+radius<top or py-radius>bottom: break
            else: spot_strength*=1-protection
        distance=np.hypot(xx-(w/2+sx*cw),yy-(h/2+sy*ch))
        spot=np.clip((radius-distance)/max(.6,unit*1.5)+.5,0,1)
        spot*=spot_strength*(.94+.06*cloud)
        spot_color=cream[None,None,:]*(1-np.clip((cloud-.5)*4,0,.45)[...,None])
        spot_color+=purple[None,None,:]*np.clip((cloud-.5)*4,0,.45)[...,None]
        if p.get('halation',0.):
            pale=cream[None,None,:]*(.96+.04*cloud[...,None])
            pale=pale*(1-np.clip((cloud-.62)*5,0,.55)[...,None])+purple*np.clip((cloud-.62)*5,0,.55)[...,None]
            spot_color=spot_color*(1-p['halation'])+pale*p['halation']
        stock=stock*(1-spot[...,None])+spot_color*spot[...,None]
        stock+=_blur(spot,5*unit)[...,None]*red*.09
        if p.get('halation',0.):
            stock+=_blur(spot,9*unit)[...,None]*purple*p['halation']*.12
    if p['dust']:
        dirt=np.clip((chips-.76)*12,0,1)*p['dust']
        # New exposure layers use sparse dust; retain the main impression's
        # original erosion and the exact legacy path when montage is disabled.
        if p.get('fragment_mix',0.):
            dirt*=1-p['fragment_mix']*(1-main)*.85
        stock*=1-dirt[...,None]
        # Sparse fine dust, neither a full-frame uniform grid nor large blobs.
        specks=(texture.random((h,w))<p['dust']*.0015)
        stock+=specks[...,None]*.2
        if texture.random()<p['dust']*.25:
            x=int(texture.integers(0,w))
            stock[:,x:x+max(1,round(unit))]*=.65
    vignette=np.clip(1-(nx*nx+ny*ny)*.75,.28,1)
    stock*=vignette[...,None]
    # Exposed pigment carries stronger grain than unexposed black stock.
    stock+=fine[...,None]*p['grain']*(.07+np.sqrt(np.maximum(stock,0))*.65)
    return np.clip(stock,0,1).astype(np.float32)
