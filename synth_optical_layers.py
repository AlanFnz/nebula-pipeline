"""Optional secondary exposures; the readable foreground is composed afterward."""
import math

import numpy as np
from PIL import Image, ImageFilter


def _blur(a, radius):
    return np.asarray(Image.fromarray(np.uint8(np.clip(a,0,1)*255)).filter(
        ImageFilter.GaussianBlur(float(max(0.,radius)))),np.float32)/255


def _field(rng, size, grid):
    return np.asarray(Image.fromarray(rng.random(grid).astype(np.float32),'F').resize(
        size,Image.Resampling.BICUBIC),np.float32)


def _stamp(sample, size, height, x, y, angle=0.):
    """Inverse projection keeps giant closeups bounded by the output canvas."""
    w,h=size; scale=max(.001,height/max(1,sample.height))
    c,s=math.cos(angle)/scale,math.sin(angle)/scale
    return np.asarray(sample.transform(size,Image.Transform.AFFINE,
        (c,s,sample.width/2-c*x-s*y,-s,c,sample.height/2+s*x-c*y),
        Image.Resampling.BILINEAR),np.float32)/255


def secondary_exposures(source, p, cut, progress, seed, reference, reading, protection,
                        red, purple, cream):
    h,w=source.shape; cw,ch=reference; unit=min(cw,ch)/720
    rng=np.random.default_rng((int(seed)+7919*(int(cut)+31))%2**32)
    mode=int(rng.integers(0,8))
    stock=np.full((h,w,3),p['stock'],np.float32)
    original=Image.fromarray(np.uint8(np.clip(source,0,1)*255))
    bounds=original.getbbox()
    if not bounds: return stock
    original=original.crop(bounds)
    sample=original
    if reading and p.get('fragment_typeface',0) and reading.text.strip():
        from synth_reading_montage import letters
        from synth_text import glyph_mask
        units=[c for c in letters(reading.text) if not c.isspace()]
        # A complete grapheme from the current word, never a fixed decorative
        # string. The primary font and its reading schedule remain untouched.
        selected=units[int(rng.integers(0,len(units)))]
        sample=glyph_mask(selected,2+int(p['fragment_typeface']),0.,1.,1,weight=700)
    else:
        # Footage and source-pixel mode use an adjustable-size source detail.
        span=max(1,round(original.width/max(1.,p['enlargement'])))
        left=int(rng.integers(0,max(1,original.width-span+1)))
        sample=original.crop((left,0,min(original.width,left+span),original.height))
    u=progress*progress*(3-2*progress)
    shift=(u-.5)*p['motion']
    x=w/2+rng.uniform(-.55,.55)*cw+shift*cw*.25
    y=h/2+rng.uniform(-.45,.45)*ch-shift*ch*.18
    height=ch*rng.uniform(.95,2.7)*p['enlargement']/3.8
    angle=rng.uniform(-.12,.12)
    red_mask=_stamp(sample,(w,h),height,x,y,angle)
    focus=(.7+rng.uniform(0,26)*p['focus']*(.3+.7*math.sin(progress*math.pi)**2))*unit
    red_mask=_blur(red_mask,focus)
    cloud=_field(rng,(w,h),(7,10))
    detail=_field(rng,(w,h),(max(4,round(ch/6)),max(4,round(cw/6))))
    # Uneven exposure leaves deep black frames between brighter fragments.
    level=(.17,.9,.65,.08,.45,.95,.32,.78)[mode]
    red_mask*=level*(.65+.35*cloud)
    yy,xx=np.mgrid[:h,:w].astype(np.float32)
    nx=(xx-w/2)/cw;ny=(yy-h/2)/ch
    a=math.radians(p['stripe_angle'])
    stripes=(np.sin((nx*math.cos(a)+ny*math.sin(a))*25+cut*.71)>.2).astype(np.float32)
    stripes=_blur(stripes,(2+7*p['focus'])*unit)*p['stripes']
    if mode in (0,3,6):
        red_mask=red_mask*.25+stripes*(.5 if mode==0 else .23)
    else:
        red_mask=np.maximum(red_mask,stripes*.07)
    stock+=red_mask[...,None]*red
    if mode in (2,4,5,7):
        # A separate registration of the original source retains its original
        # typeface, giving a second ink impression behind the readable word.
        px=w/2+rng.uniform(-.35,.35)*cw-shift*cw*.2
        py=h/2+rng.uniform(-.35,.35)*ch
        span=min(original.width,max(1,round(original.height*rng.uniform(.7,1.5))))
        left=int(rng.integers(0,max(1,original.width-span+1)))
        detail_sample=original.crop((left,0,left+span,original.height))
        violet=_stamp(detail_sample,(w,h),ch*rng.uniform(1.2,2.6),px,py,-angle)
        violet=_blur(violet,(.6+3*p['focus'])*unit)
        # Broad chipped ink islands, rather than a porous texture at every pixel.
        islands=_field(rng,(w,h),(23,31))
        patches=np.clip((cloud*.8+islands*.2-.52)*30,0,1)*p['pale_ink']
        chipped=np.clip((detail-.91)*12,0,1)*p['damage']*.5
        color=purple[None,None,:]*(1-patches[...,None])+cream*patches[...,None]
        opacity=violet*(1-chipped)*rng.uniform(.55,.95)
        stock=stock*(1-opacity[...,None]) + color*opacity[...,None]
    # Background changes never introduce a new opaque label or cover the main
    # impression. The original glyph separation is applied by the caller.
    stock*=p['overprint']*(1-protection*.25)
    bleed=p.get('halation',0.)
    if bleed:
        stock+=_blur(np.max(stock,axis=2),7*unit)[...,None]*red*bleed*.16
    return np.clip(stock,0,1)
