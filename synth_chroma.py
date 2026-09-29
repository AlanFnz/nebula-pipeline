"""Source-independent color exposures, displaced slices and screen phosphors."""
import colorsys
import math

import numpy as np
from PIL import Image, ImageFilter


def _color(hue, saturation, value=1.):
    return np.array(colorsys.hsv_to_rgb(hue % 1, saturation, value), dtype=np.float32)


def render_chroma_print(arr, p, reference_size):
    if not p['mix']: return arr
    source = np.maximum(arr, 0.)
    if p.get('softness', 0.):
        # Defocus the image before printing; phosphor lines are applied later
        # and remain visible instead of being erased by the final raster blur.
        source = np.asarray(Image.fromarray(np.uint8(np.clip(source*255,0,255))).filter(
            ImageFilter.GaussianBlur(p['softness']*min(reference_size)/720)),dtype=np.float32)/255
    luma = source @ np.array((.2126,.7152,.0722), dtype=np.float32)
    if p['detail']:
        blurred = np.asarray(Image.fromarray(np.uint8(np.clip(luma*255,0,255))).filter(
            ImageFilter.GaussianBlur(p['detail_radius']*min(reference_size)/720)),dtype=np.float32)/255
        luma = np.maximum(0,luma+(luma-blurred)*p['detail'])
    tone = np.clip((luma * 2**p['exposure'] - p['black']) / max(.01,p['white']-p['black']),0,1)
    tone = tone ** (1/p['gamma'])
    folded = np.where(tone > p['solarize_point'],
                      p['solarize_point'] - (tone-p['solarize_point']), tone)
    tone = np.maximum(0, tone*(1-p['solarize']) + folded*p['solarize'])
    if p.get('solarize_lift',0.) and p['solarize']:
        gain = 1+(1/p['solarize_point']-1)*p['solarize_lift']*p['solarize']
        tone = np.clip(tone*gain,0,1)
    # Cyan (or any chosen hue) in the mids, near-white highlights, deep black.
    base = _color(p['mid_hue'],p['mid_saturation'])
    white = _color(p['white_hue'],p['white_saturation'])
    highlight = np.clip((tone-p['highlight_start'])/max(.01,1-p['highlight_start']),0,1)
    palette = base + highlight[...,None]*(white-base)
    warm = np.clip(((source[...,0]-source[...,1]) / np.maximum(.01,source[...,0]+source[...,1])
                    - p['warm_threshold']) / .15,0,1) * p['warm_color']
    accent = _color(p['warm_hue'],p['warm_saturation'])
    palette = palette*(1-warm[...,None]) + accent*warm[...,None]
    out = tone[...,None]*palette
    out = out*(1-p['source_color']) + np.clip(arr,0,1)*p['source_color']
    return arr*(1-p['mix']) + out*p['mix']


def slice_events(p, time, speed, seed):
    """Event layout is independent of render dimensions and request order."""
    clock = time * speed
    if p['cadence']: clock = math.floor(clock*p['cadence']+1e-8)/p['cadence']
    cycle = clock/p['period'] + p['phase']
    tick = math.floor(cycle)
    rng = np.random.default_rng(np.random.SeedSequence((seed,tick & 0xffffffffffffffff,627)))
    if rng.random() >= p['activity']: return ()
    progress = cycle-tick
    events = []
    for _ in range(p['count']):
        center = rng.uniform(-.1,1.1) + (progress-.5)*p['travel']*rng.choice((-1,1))
        height = p['height']*rng.uniform(.45,1.4)
        dx = rng.uniform(-1,1)*p['shift_x']
        dy = rng.uniform(-1,1)*p['shift_y']
        zoom = 1+rng.uniform(-1,1)*p['scale']
        tint = rng.random() < p['color_chance']
        events.append((float(center),float(height),float(dx),float(dy),float(zoom),tint))
    return tuple(events)


def slice_envelope(p, time, speed):
    """Fade event edges on the same held clock that drives slice travel."""
    fade = min(.5, max(0., p.get('envelope', 0.)))
    if not fade:
        return 1.
    clock = time * speed
    if p['cadence']: clock = math.floor(clock*p['cadence']+1e-8)/p['cadence']
    cycle = clock/p['period'] + p['phase']
    progress = cycle-math.floor(cycle)
    edge = min(1., progress/fade, (1-progress)/fade)
    return edge*edge*(3-2*edge)


def fragment_mask(p, rows, width, height, center, extent, time, speed, seed, index):
    """Bounded, stepped image fragments, on a resolution-independent event grid.

    A separate random stream leaves legacy slice positions and tint choices
    unchanged. Neutral settings bypass this path entirely.
    """
    clock = time*speed
    if p['cadence']: clock = math.floor(clock*p['cadence']+1e-8)/p['cadence']
    tick = math.floor(clock/p['period']+p['phase'])
    rng = np.random.default_rng(np.random.SeedSequence((seed,tick & 0xffffffffffffffff,891,index)))
    angle = math.radians(p.get('angle',0.))
    x = (np.arange(width,dtype=np.float32)+.5-width/2)/height
    y = ((np.arange(height,dtype=np.float32)+.5-height/2)/height)[:,None]
    u = x[None,:]*math.cos(angle)+y*math.sin(angle)
    span = width/height
    cx = rng.uniform(-.32,.32)*span
    half = p.get('width',1.)*span*rng.uniform(.65,1.3)*.5
    breakup = p.get('edge_breakup',0.)
    # The steps belong to the event, not individual pixels or a moving tile.
    columns = np.clip(((u/span+.75)/1.5*9).astype(int),0,8)
    bands = np.clip(((rows-center)/max(extent,.001)+.75)/1.5*5,0,4).astype(int)
    top = rng.uniform(-.5,.5,9).astype(np.float32)[columns]*extent*breakup
    bottom = rng.uniform(-.5,.5,9).astype(np.float32)[columns]*extent*breakup
    left = rng.uniform(-.3,.3,5).astype(np.float32)[bands]*half*breakup
    right = rng.uniform(-.3,.3,5).astype(np.float32)[bands]*half*breakup
    distance = np.minimum(rows-(center-extent*.5+top),center+extent*.5+bottom-rows)
    if p.get('width',1.) < 1.:
        distance = np.minimum(distance,np.minimum(u-(cx-half+left),cx+half+right-u))
    return np.clip(distance/max(1/height,p['softness'])+.5,0,1)


def render_slice_echo(arr, p, time, speed, seed, reference_size):
    """Main slices plus an optional, independently timed set of image flashes."""
    if not p.get('flash_opacity',0.) or not p['mix']:
        return _render_slice_pass(arr,p,time,speed,seed,reference_size)
    out = _render_slice_pass(arr,dict(p,mix=1.),time,speed,seed,reference_size)
    clock = time*speed
    if p['cadence']: clock = math.floor(clock*p['cadence']+1e-8)/p['cadence']
    cycle = clock/p['flash_period']+p['phase']
    elapsed = (cycle-math.floor(cycle))*p['flash_period']
    duration = min(p['flash_period'],p['flash_seconds'])
    if elapsed < duration:
        fade = 1-elapsed/duration
        fade = fade*fade*(3-2*fade)
        flashes = dict(p, mix=1., opacity=p['flash_opacity']*fade,
            period=p['flash_period'], envelope=0., travel=0.,
            count=p['flash_count'], width=p['flash_width'], height=p['flash_height'],
            edge_breakup=p['flash_breakup'], negative=p['flash_negative'])
        flash_seed = int(np.random.SeedSequence((seed,1763)).generate_state(1)[0])
        out = _render_slice_pass(out,flashes,time,speed,flash_seed,reference_size)
    return arr*(1-p['mix'])+out*p['mix']


def _render_slice_pass(arr, p, time, speed, seed, reference_size):
    if not p['mix'] or not p['opacity']: return arr
    events = slice_events(p,time,speed,seed)
    if not events: return arr
    h,w = arr.shape[:2]; cw,ch = reference_size
    rows = ((np.arange(h,dtype=np.float32)+.5)/h)[:,None]
    if p.get('angle', 0.):
        angle = math.radians(p['angle'])
        # Rotate in pixel space, so the same angle stays the same in Stories,
        # square and landscape canvases. This tilts the seam, not the source.
        columns = (np.arange(w,dtype=np.float32)+.5-w/2)/h
        rows = .5+(rows-.5)*math.cos(angle)-columns[None,:]*math.sin(angle)
    envelope = slice_envelope(p,time,speed)
    source = Image.fromarray(np.uint8(np.clip(arr*255,0,255)))
    out = arr.copy()
    for index,(center,height,dx,dy,zoom,tint) in enumerate(events):
        distance = np.abs(rows-center)
        mask = np.clip((height*.5-distance)/max(1/h,p['softness'])+.5,0,1)
        if p.get('width',1.) < 1. or p.get('edge_breakup',0.):
            mask = fragment_mask(p,rows,w,h,center,height,time,speed,seed,index)
        if not mask.any(): continue
        shifted = source.transform((w,h),Image.Transform.AFFINE,
            (1/zoom,0,w/2-(w/2+dx*cw)/zoom,0,1/zoom,h/2-(h/2+dy*ch)/zoom),
            Image.Resampling.BILINEAR)
        echo = np.asarray(shifted,dtype=np.float32)/255
        coverage = None
        if p.get('luma_mask', 0.):
            light = echo @ np.array((.2126,.7152,.0722),dtype=np.float32)
            coverage = 1-p['luma_mask']+p['luma_mask']*np.clip(light,0,1)
        if p.get('negative',0.):
            # Reverse the exposed image, before tinting. Coverage still comes
            # from the original image so black gaps need not turn into plates.
            echo = echo*(1-p['negative'])+(1-echo)*p['negative']
        if tint:
            light = echo.max(axis=2)
            color = _color(p['hue'],p['saturation'])
            if p.get('highlight_protect', 0.):
                highlight = np.clip((light-.35)/.65,0,1)
                highlight = highlight*highlight*(3-2*highlight)*p['highlight_protect']
                color = color + highlight[...,None]*(1-color)
            colored = light[...,None]*color
            echo = echo*(1-p['color_mix']) + colored*p['color_mix']
        echo *= 2**p['exposure']
        # Blend both cut slices and overlapping exposures from the actual image.
        echo = echo*(1-p['screen']) + (1-(1-out)*(1-echo))*p['screen']
        alpha = mask[...,None]*p['opacity']
        if p.get('envelope', 0.): alpha *= envelope
        if coverage is not None: alpha = alpha*coverage[...,None]
        out = out*(1-alpha)+echo*alpha
    return arr*(1-p['mix'])+out*p['mix']


def render_screen_mesh(arr, p, time, speed, seed, reference_size):
    if not p['mix']: return arr
    h,w = arr.shape[:2]; unit = min(reference_size)/720
    y,x = np.mgrid[:h,:w].astype(np.float32)
    angle = math.radians(p['angle'])
    u = x*math.cos(angle) - y*math.sin(angle)
    v = x*math.sin(angle) + y*math.cos(angle)
    clock = time*speed
    tick = math.floor(clock*p['cadence']+1e-8) if p['cadence'] else 0
    held_clock = tick/p['cadence'] if p['cadence'] else 0.
    u += p['bend']*unit*(np.sin(v/max(1,min(reference_size))*7+held_clock*.15)
                          + .12*np.sin(v/max(.1,unit)*.075))
    rng = np.random.default_rng(np.random.SeedSequence((seed,tick & 0xffffffffffffffff,942)))
    pitch = max(.1,p['pitch']*unit)
    # Fade frequencies above Nyquist in small previews, avoiding false moire.
    visibility = float(np.clip(pitch/2-0.5,0,1))
    phase = (u/pitch + rng.uniform(-1,1)*p['jitter'] + p['phase'])*math.tau
    wear = p.get('wear', 0.)
    if wear:
        # Small row registration errors and uneven phosphor points create a
        # filmed surface. Zero preserves the original pattern and RNG sequence.
        phase += wear*(.6*rng.normal(size=(h,1)).astype(np.float32)
                       + .5*rng.normal(size=(h,w)).astype(np.float32))
    # Keep the mean absorption when suppressing subpixel detail; otherwise a
    # small preview becomes brighter than the exported phosphor pattern.
    luminance = 1-p['strength']*(.5-.5*visibility*np.cos(phase))
    offsets = np.array((0.,-math.tau/3,math.tau/3),dtype=np.float32)
    triad = np.cos(phase[...,None]+offsets)
    phosphor = 1-p['rgb']*(.5-.5*visibility*triad)
    # Overlapping column and RGB masks otherwise introduce a red cast at full
    # resolution which vanishes when the fine detail is filtered for preview.
    mean = (1-p['strength']/2)*(1-p['rgb']/2)
    balance = mean/(mean+p['strength']*p['rgb']*visibility**2/8*np.cos(offsets))
    row_pitch = max(.1,p['row_pitch']*unit)
    row_visibility = float(np.clip(row_pitch/2-.5,0,1))
    rows = 1-p['rows']*(.5+.5*row_visibility*np.cos(v/row_pitch*math.tau))
    out = arr*(luminance*rows)[...,None]*phosphor*balance*2**p['exposure']
    if wear:
        emission = rng.normal(1.,.16*wear,(h,w,1)).astype(np.float32)
        out *= np.clip(emission,0.,2.)
    if p['grain']:
        noise = rng.normal(0,p['grain'],(h,w,1)).astype(np.float32)
        out += noise*np.sqrt(np.maximum(0,arr.mean(axis=2,keepdims=True)))
    if p['softness']:
        out = np.asarray(Image.fromarray(np.uint8(np.clip(out*255,0,255))).filter(
            ImageFilter.GaussianBlur(p['softness']*unit)),dtype=np.float32)/255
    return arr*(1-p['mix'])+out*p['mix']
