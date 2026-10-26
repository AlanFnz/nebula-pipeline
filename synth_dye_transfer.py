"""Deterministic dye-transfer printing of arbitrary source pixels.

Wording and cuts belong to compositions. No reference frames, typography or
study-specific time switches are used in this image treatment.
"""
import colorsys
import math

import numpy as np
from PIL import Image, ImageFilter


def modules(Module, P):
    return (Module('dye_transfer', 'Dye transfer',
        'Saturated film stock, dark or pale impressions, vertical exposure drag and uneven registration.', (
        P('paper_hue', 'Stock hue', .014, 0, 1, .01),
        P('paper_saturation', 'Stock saturation', 1., 0, 1, .01),
        P('paper_light', 'Stock brightness', 1., 0, 1.2, .01),
        P('ink_hue', 'Ink hue', .015, 0, 1, .01),
        P('ink_saturation', 'Ink saturation', .75, 0, 1, .01),
        P('ink_light', 'Ink brightness', .075, 0, 1, .01),
        P('wash', 'Uneven exposure', .14, 0, 1, .01),
        P('halo', 'Exposure halo', 0., 0, 2, .05, 'Light spills around the impression, leaving its ink center dark.'),
        P('dye', 'Edge dye', .32, 0, 1, .01),
        P('scale', 'Impression scale', 1., .1, 8, .01),
        P('x', 'Position X', 0., -2, 2, .01),
        P('y', 'Position Y', 0., -2, 2, .01),
        P('angle', 'Impression angle', 0., -180, 180, 1),
        P('weave', 'Gate weave', .002, 0, .05, .001),
        P('warp', 'Wet ink movement', 1.4, 0, 30, .1, 'Pixels at a 720-pixel canvas width.'),
        P('drag', 'Vertical exposure drag', .06, 0, .6, .01, 'Length of a blurred secondary exposure relative to canvas height.'),
        P('drag_mix', 'Dragged impression', .18, 0, 1, .01),
        P('softness', 'Optical softness', .6, 0, 12, .1, 'Pixels at a 720-pixel canvas width.'),
        P('choke', 'Thin ink edges', 0., 0, 4, .1, 'Reduce ink buildup in thick lettering. Pixels at a 720-pixel canvas width.'),
        P('erosion', 'Ink erosion', .055, 0, 1, .01),
        P('grain', 'Film grain', .016, 0, .2, .005),
        P('dust', 'Dust & scratches', .13, 0, 1, .01),
        P('opening', 'Gate opening', 1.2, 0, 1.5, .01, 'Zero is black; one fills the frame. Lower values reveal a rough vertical aperture.'),
        P('gate_x', 'Gate position', .5, -1, 2, .01),
        P('gate_softness', 'Gate softness', .025, .001, .2, .001),
        P('level', 'Exposure level', 1., 0, 1, .01, 'Fade the whole impression into unexposed stock.'),
        P('cadence', 'Print cadence', 15., 1, 60, 1),
        # Opt-in optical finish: zero retains the original printing contract.
        P('emulsion', 'Mottled emulsion', 0., 0, 1, .01, 'Unequal film density and coarse, fine and rubbed stock texture.'),
        P('streaks', 'Exposure streaks', 0., 0, 1, .01, 'Irregular vertical density bands in both the stock and the impression.'),
        P('edge_bloom', 'Edge bloom', 0., 0, 1, .01, 'A narrow light rim around the ink, as in an overexposed print.'),
        P('registration', 'Local registration', 0., 0, 1, .01, 'Small uneven bends and offsets within the impression, without moving the entire picture.'),
        P('focus_flutter', 'Focus flutter', 0., 0, 6, .1, 'Irregular changes in optical focus. Pixels at a 720-pixel canvas width.'),
        P('shutter', 'Shutter pull', 0., -1, 1, .01, 'Drag parts of the impression vertically during a cut. Negative pulls upward; positive pulls downward. Zero keeps it still.'),
    )),)


def _field(rng, size, grid):
    return np.asarray(Image.fromarray(rng.random(grid).astype(np.float32), 'F').resize(
        size, Image.Resampling.BICUBIC), np.float32)


def _blur(a, radius):
    if radius <= .01: return a
    return np.asarray(Image.fromarray(np.uint8(np.clip(a, 0, 1)*255)).filter(
        ImageFilter.GaussianBlur(float(radius))), np.float32)/255


def _sample(a, x, y):
    """Subpixel sampling with unexposed pixels beyond the film edge (no wrap)."""
    h, w = a.shape
    valid = (x >= 0) & (x <= w-1) & (y >= 0) & (y <= h-1)
    x = np.clip(x, 0, w-1); y = np.clip(y, 0, h-1)
    x0 = x.astype(np.int32); y0 = y.astype(np.int32)
    x1 = np.minimum(x0+1, w-1); y1 = np.minimum(y0+1, h-1)
    fx = x-x0; fy = y-y0
    return ((a[y0, x0]*(1-fx)+a[y0, x1]*fx)*(1-fy)
            +(a[y1, x0]*(1-fx)+a[y1, x1]*fx)*fy)*valid


def _density(size, reference, seed, clock):
    """Slowly evolving stock plus reprinted fine texture, independent of v1 RNG."""
    cw, ch = reference
    cell = math.floor(clock*.8)
    blend = clock*.8-cell
    blend = blend*blend*(3-2*blend)
    fields = []
    for step in (cell, cell+1):
        rng = np.random.default_rng((int(seed)+201517+step*7919)%2**32)
        cloud = _field(rng, size, (5, 8))-.5
        streak = _field(rng, size, (3, 14))-.5
        fields.append((cloud, streak))
    cloud = fields[0][0]*(1-blend)+fields[1][0]*blend
    streak = fields[0][1]*(1-blend)+fields[1][1]*blend
    rng = np.random.default_rng((int(seed)+51719+math.floor(clock*15)*3253)%2**32)
    rubbed = _field(rng, size, (max(2, round(ch/2)), max(2, round(cw/8))))-.5
    speckle = _field(rng, size, (max(2, round(ch/3)), max(2, round(cw/3))))-.5
    return cloud, streak, rubbed, speckle


def render_dye_transfer(arr, p, seconds, speed, seed, reference):
    h,w=arr.shape[:2]; cw,ch=reference; unit=cw/720
    frame=math.floor(max(0., seconds*speed)*p['cadence']+1e-7)
    rng=np.random.default_rng((int(seed)+frame*104729)%2**32)
    # Three exposure bands, changing each held frame, with fine grain on top.
    cloud=_field(rng,(w,h),(5,9)); columns=_field(rng,(w,h),(3,39))
    fine=rng.normal(0,1,(h,w)).astype(np.float32)
    yy,xx=np.mgrid[:h,:w].astype(np.float32)
    nx=(xx-w/2)/cw; ny=(yy-h/2)/ch
    optical = any(p.get(k, 0) for k in ('emulsion', 'streaks', 'edge_bloom', 'registration', 'focus_flutter', 'shutter'))
    if optical:
        optical_clock = frame/p['cadence']
        density, streak, rubbed, speckle = _density((w,h), reference, seed, optical_clock)
    a=math.radians(p['angle']); c,s=math.cos(a),math.sin(a)
    dx,dy=rng.normal(0,p['weave'],2)
    cx=w/2+(p['x']+dx)*cw; cy=h/2+(p['y']+dy)*ch
    source=Image.fromarray(np.uint8(np.max(np.clip(arr,0,1),axis=2)*255))
    scale=max(.01,p['scale'])
    ink=np.asarray(source.transform((w,h),Image.Transform.AFFINE,
        (c/scale,s/scale,w/2-(c*cx+s*cy)/scale,
         -s/scale,c/scale,h/2-(-s*cx+c*cy)/scale),Image.Resampling.BICUBIC),np.float32)/255
    if p['choke']:
        distance=p['choke']*unit
        radius=max(1,math.ceil(distance))
        thin=np.asarray(Image.fromarray(np.uint8(ink*255)).filter(ImageFilter.MinFilter(radius*2+1)),np.float32)/255
        ink=ink+(thin-ink)*min(1.,distance/radius)
    if p['warp']:
        shift=(cloud-.5)*p['warp']*unit
        # Clamp the sampling coordinates, never wrap the opposite frame edge.
        sx=np.clip(np.rint(xx+shift),0,w-1).astype(int)
        sy=np.clip(np.rint(yy+shift*.45),0,h-1).astype(int)
        ink=ink[sy,sx]
    if p['erosion']:
        chips=_field(rng,(w,h),(max(2,round(ch/2)),max(2,round(cw/2))))
        ink*=1-np.clip((chips-.55)*3,0,1)*p['erosion']
    if p.get('registration', 0):
        # Deform the local print, not the background or the overall framing.
        local = p['registration']*unit
        dx = (cloud-.5)*10 + streak*5 + rubbed*.6
        dy = (columns-.5)*10 + density*4
        ink = _sample(ink, xx+local*dx, yy+local*dy).astype(np.float32)
    focus = p['softness']
    if p.get('focus_flutter', 0):
        phase = seed%1021*.017
        flutter = (.5+.5*math.sin(optical_clock*7.13+phase)*math.sin(optical_clock*2.37+1.7))**3
        focus += p['focus_flutter']*flutter
    ink=_blur(ink,focus*unit)
    # An anisotropic optical exposure: narrow horizontally, long vertically.
    smear=ink
    if p['drag'] and p['drag_mix']:
        compressed=Image.fromarray(np.uint8(ink*255)).resize((w,max(1,h//16)),Image.Resampling.BILINEAR)
        smear=np.asarray(compressed.filter(ImageFilter.GaussianBlur(max(.1,p['drag']*ch/16))).resize((w,h),Image.Resampling.BILINEAR),np.float32)/255
    impression=np.maximum(ink,smear*p['drag_mix'])
    if p.get('shutter', 0):
        pull = p['shutter']*ch
        # Separate columns slip by different distances, then leave a dense,
        # directional exposure trail. Sampling never imports the opposite edge.
        gates = np.clip((streak+.05)*4, 0, 1)
        # Keep most of the letter recognizable. Only narrow shutter bands
        # lose registration; the exposed streak extends farther than the body.
        displaced = _sample(ink, xx, yy-pull*gates*.025)
        # A causal exposure envelope makes a continuous streak. Discrete
        # translated copies leave recognizably repeated letter silhouettes.
        dragged = np.zeros_like(ink)
        carried = np.zeros(w, np.float32)
        decay = math.exp(-1/max(1., abs(pull)*.55))
        rows = range(h) if pull > 0 else range(h-1,-1,-1)
        for row in rows:
            carried = np.maximum(ink[row], carried*decay)
            dragged[row] = carried
        strength = min(1., abs(p['shutter'])*3)
        rubbed_trail = dragged*gates*np.clip(1+rubbed*1.6+speckle*.2, .35, 1.)
        impression = impression*(1-strength)+np.maximum(displaced,rubbed_trail)*strength
    paper=np.array(colorsys.hsv_to_rgb(p['paper_hue'],p['paper_saturation'],p['paper_light']),np.float32)
    pigment=np.array(colorsys.hsv_to_rgb(p['ink_hue'],p['ink_saturation'],p['ink_light']),np.float32)
    exposure=.8*(cloud-.5)+.2*(columns-.5)
    stock=np.broadcast_to(paper,(h,w,3)).copy()
    stock*=1+p['wash']*exposure[...,None]
    # Unequal film density and a low warm exposure at the gate's lower edge.
    stock+=p['wash']*np.exp(-((ny-.52)/.13)**2)[...,None]*np.array([.12,.065,.008],np.float32)
    if p.get('emulsion', 0):
        warm_edge = np.exp(-((ny-.52)/.15)**2-(nx/.42)**2)
        stock -= warm_edge[...,None]*p['emulsion']*np.array([0.,.02,.32],np.float32)
    stock-=np.maximum(0,smear-ink)[...,None]*p['drag_mix']*.3
    if p['halo']:
        bloom=_blur(ink,max(.2,14*unit))*.7+smear*.7
        stock+=bloom[...,None]*p['halo']*np.array([1.,.98,.97],np.float32)
    result=stock*(1-impression[...,None])+pigment*impression[...,None]
    if optical:
        if p.get('emulsion', 0) or p.get('streaks', 0):
            # Multiplicative density retains the selected hue, including red
            # stock whose leading channel would otherwise clip to a flat field.
            density_loss = p.get('emulsion',0)*np.clip(.085-density*.20-rubbed*.055-speckle*.045,0,.35)
            density_loss += p.get('streaks',0)*np.clip(.06-streak*.32-rubbed*.018,0,.35)
            band = np.clip((.10-streak+rubbed*.06+speckle*.04)*2.3,0,1)**2
            density_loss += p.get('streaks',0)**3 * band*.85
            density_loss = np.minimum(density_loss, .94)
            result *= 1-density_loss[...,None]
            result += (speckle*p.get('emulsion',0)*.015)[...,None]
        if p.get('edge_bloom', 0):
            rim_light = np.clip(_blur(impression,1.8*unit)-impression,0,1)
            result += rim_light[...,None]*p['edge_bloom']*1.7
    rim=np.clip(_blur(ink,2.5*unit)-ink,0,1)
    result+=rim[...,None]*p['dye']*np.array([.45,.07,.015],np.float32)
    if p['dust']:
        dust=np.clip((_field(rng,(w,h),(max(2,round(ch/3)),max(2,round(cw/3))))-.9)*7,0,1)
        result*=1-dust[...,None]*p['dust']*.5
        if rng.random()<p['dust']*.6:
            x=int(rng.integers(0,w));result[:,x:x+max(1,round(unit))]*=1-p['dust']*.22
    result+=fine[...,None]*p['grain']*(.15+.85*np.sqrt(np.maximum(result,0)))
    result+=(rng.random((h,w,3),dtype=np.float32)-.5)*p['grain']*.25
    rough=_field(rng,(w,h),(max(2,h//8),2))
    edge=np.abs(nx+.5-p['gate_x'])+(rough-.5)*.018
    gate=np.clip((p['opening']/2-edge)/p['gate_softness'],0,1)
    if p['opening']>=1.2: gate=np.ones_like(gate)
    result*=gate[...,None]*p['level']
    return np.clip(result,0,1).astype(np.float32)
