"""Seekable image-signal repetition: horizontal resampling, never frame history.

The source supplies every repeated fragment. Oscillators bend the scan phase;
soft image keys retain the original outline. Distances share a 720px reference.
"""
import colorsys
import math
import numpy as np
from synth_modulation import _blur, _field, _noise, _smooth, signal_region, _row_sample


def modules(Module, P):
    return (Module('signal_repetition', 'Signal repetition',
        'Fold the image signal into moving repeated fragments inside a soft image selection.', (
        P('input', 'Signal input', 1, 0, 1, 1, choices=('Current image', 'Original source')),
        P('region', 'Region', 0, 0, 3, 1, 'Video foreground requires imported footage and runs entirely on this Mac. The other selections work with every source.', choices=('Whole image', 'Highlights', 'Color range', 'Video foreground')),
        P('key_hue', 'Selected hue', .6, 0, 1, .01),
        P('key_width', 'Hue tolerance', .09, 0, .5, .01),
        P('key_saturation', 'Minimum saturation', .12, 0, .9, .01),
        P('key_floor', 'Minimum brightness', .08, 0, .9, .01),
        P('key_softness', 'Selection softness', .12, .01, .5, .01),
        P('key_invert', 'Invert selection', 0, 0, 1, 1, choices=('Off', 'On')),
        P('show_key', 'View', 0, 0, 1, 1, choices=('Result', 'Selection')),
        P('spacing', 'Repeat spacing', 36., 8, 240, 1, 'Pixels at a 720-pixel reference edge. Smaller values produce more repetitions.'),
        P('sample_width', 'Sample width', 250., 20, 720, 5, 'Width of the source signal compressed into each repeat.'),
        P('sample_center', 'Sample position', .5, 0, 1, .01, 'Horizontal position within the selected region.'),
        P('contour', 'Follow silhouette', .65, 0, 1, .01, 'Bend the repeated rows with the outline of the selection.'),
        P('outline_warp', 'Outline movement', 0., 0, 40, 1, 'Bend the selected outline with the scan signal. Reference pixels.'),
        P('edge_echo', 'Outline echoes', 0., 0, 1, .01),
        P('edge_distance', 'Echo spacing', 12., 1, 60, 1, 'Reference pixels between the two fading outline copies.'),
        P('row_height', 'Band height', 65., 8, 240, 1),
        P('row_breakup', 'Band irregularity', .7, 0, 1, .01, 'Vary the shape and phase of neighboring scan bands.'),
        P('row_lines', 'Row interruptions', .4, 0, 1, .01),
        P('wave', 'Row bending', 16., 0, 100, 1),
        P('drift', 'Horizontal travel', 12., -120, 120, 1, 'Reference pixels per second.'),
        P('instability', 'Phase instability', .35, 0, 1, .01),
        P('rate', 'Motion speed', 1., 0, 5, .05, 'Zero freezes the pattern while footage continues.'),
        P('cadence', 'Motion FPS', 0., 0, 60, 1, 'Zero moves continuously.'),
        P('relief', 'Contour contrast', 2., 0, 5, .05),
        P('detail', 'Original detail', .16, 0, 1, .01),
        P('hue', 'Signal hue', .62, 0, 1, .01),
        P('saturation', 'Signal saturation', .7, 0, 1, .01),
        P('exposure', 'Signal exposure', 0., -3, 3, .05),
        P('fringe', 'Color fringe', .7, 0, 2, .01),
        P('color_slips', 'Color-lock slips', .2, 0, 1, .01, 'Brief magenta faults that travel through the repeated signal.'),
        P('fringe_hue', 'Fringe hue', .16, 0, 1, .01),
        P('edge_width', 'Fringe width', 1.5, .25, 8, .25),
        P('outside_mix', 'Replace outside selection', 0., 0, 1, .01, 'Zero keeps the rest of your picture. One replaces it with the background color.'),
        P('outside_level', 'Background brightness', .6, 0, 1, .01),
        P('outside_hue', 'Background hue', .62, 0, 1, .01),
        P('outside_saturation', 'Background saturation', .12, 0, 1, .01),
        P('mix', 'Mix', 1., 0, 1, .01),
    )),)


def _sample_rows(arr, x):
    """Linear source sampling with clamped boundaries, including narrow canvases."""
    h, w = arr.shape[:2]
    x = np.clip(x, 0, w-1)
    lo = np.floor(x).astype(np.int32)
    f = x-lo
    if arr.ndim == 3: f = f[..., None]
    rows = np.arange(h)[:, None]
    return arr[rows, lo]*(1-f)+arr[rows, np.minimum(lo+1,w-1)]*f


def render_signal_repetition(arr, p, time, speed, seed, reference_size, original=None, source_mask=None):
    if not p['mix']: return arr
    source = original if p['input'] and original is not None else arr
    key_params = dict(p, fade=0., region=0 if p['region'] == 3 else p['region'])
    mask, luma = signal_region(source, key_params, reference_size)
    if p['region'] == 3:
        if source_mask is None: raise ValueError('Video foreground selection needs imported footage and its foreground mask.')
        from PIL import Image
        mask = np.asarray(source_mask.resize((arr.shape[1],arr.shape[0]), Image.Resampling.BILINEAR),dtype=np.float32)/255
        if p['key_invert']: mask = 1-mask
    if p['show_key']: return np.repeat(mask[...,None],3,axis=2)
    h,w = mask.shape
    unit = min(reference_size)/720
    clock = time*speed*p['rate']
    if p['cadence']: clock = math.floor(clock*p['cadence']+1e-8)/p['cadence']
    y = (np.arange(h,dtype=np.float32)+.5)/unit
    x = (np.arange(w,dtype=np.float32)+.5)/unit
    active = mask > .5
    left = np.argmax(active,axis=1).astype(np.float32)/unit
    right = (w-1-np.argmax(active[:,::-1],axis=1)).astype(np.float32)/unit
    exists = active.any(axis=1)
    left = np.where(exists,left,0.)
    right = np.where(exists,right,(w-1)/unit)
    # Slowly coupled oscillators make neighboring bands diverge and reunite.
    band = y/p['row_height']
    # Uneven phase bands keep the signal from becoming a uniform wallpaper.
    band += p['row_breakup']*.45*np.sin(y*.022+np.sin(y*.009))
    cell = np.floor(band)
    bend = np.sin(band*math.tau+clock*1.3)
    bend = bend*(1-p['row_breakup']) + p['row_breakup']*(2/np.pi*np.arcsin(bend))
    band_phase = (_noise(cell,0,seed+43)-.5)*p['row_breakup']*p['spacing']
    phase = p['wave']*(bend+.35*np.sin(band*3.3-clock*2.1)) + band_phase
    phase += p['instability']*p['spacing']*(_field(band*.6,clock*1.4,seed)-.5)
    phase += clock*p['drift'] + left*p['contour']
    scan_row = np.floor(y/2.5)
    phase += (_noise(scan_row,0,seed+321)-.5)*p['spacing']*.16*p['row_lines']
    phase += np.sin(y*.91+clock*2.3)*p['row_lines']*.7
    spacing = p['spacing']*(1+p['row_breakup']*.18*(_noise(cell,0,seed+71)-.5)*2)
    cycle = (x[None,:]-phase[:,None])/spacing[:,None]
    # Each cell samples actual source pixels. No procedural pattern is pasted on.
    center = left+(right-left)*p['sample_center']
    sx = (center[:,None]+((cycle % 1)-.5)*p['sample_width'])*unit
    # Keep only selected signal when reading across its edge.
    relief_luma = np.clip(luma+(luma-_blur(luma,8*unit))*p['relief']*2,0,1)
    selected = np.stack(((relief_luma*.7+.22)*mask,mask),axis=2)
    sampled = _sample_rows(selected,sx)
    value = sampled[...,0]
    delta = max(.25,p['edge_width'])*unit*p['sample_width']/p['spacing']
    ahead = _sample_rows(selected,sx+delta)[...,0]
    behind = _sample_rows(selected,sx-delta)[...,0]
    ridge = np.clip(np.abs(ahead-behind)*p['relief']*2.5,0,1)
    tone = np.clip(.22+value*.85+ridge*.12,0,1)
    blue = np.array(colorsys.hsv_to_rgb(p['hue'],p['saturation'],1.),dtype=np.float32)
    accent = np.array(colorsys.hsv_to_rgb(p['fringe_hue'],.8,1.),dtype=np.float32)
    cyan = np.array(colorsys.hsv_to_rgb((p['hue']-.1)%1,.65,1.),dtype=np.float32)
    signal = tone[...,None]*blue
    warm = np.clip(np.maximum(ahead-value,0)*p['fringe']*p['relief']*3,0,.85)[...,None]
    cool = np.clip(np.maximum(behind-value,0)*p['fringe']*p['relief']*2,0,.8)[...,None]
    signal = signal*(1-warm)+accent*warm*.82
    signal = signal*(1-cool)+cyan*cool*.8
    if p['color_slips']:
        faults = _noise(np.floor(cycle),cell[:,None],seed+int(math.floor(clock*13))*31)
        fault = _smooth(1-p['color_slips']*.13,1.,faults)[...,None]
        magenta = np.array((.7,.08,.4),dtype=np.float32)
        signal = signal*(1-fault)+tone[...,None]*magenta*fault
    signal *= (.7+.3*sampled[...,1,None])
    interrupted = _smooth(.91,.99,band % 1)*p['row_lines']
    signal *= (1-interrupted[:,None,None])
    striation = (.5+.5*np.sin(y*math.tau/3.4+np.sin(y*.023)))
    striation *= .25+.75*_noise(scan_row,0,seed+77)
    signal *= (1-p['row_lines']*.42*striation[:,None,None])
    signal += (np.sin(y*math.tau/3.5+clock*2)*.5+.5)[:,None,None]*p['row_lines']*.035*blue
    signal = signal*(1-p['detail'])+source*p['detail']
    signal *= 2**p['exposure']
    background_color = np.array(colorsys.hsv_to_rgb(p['outside_hue'],p['outside_saturation'],p['outside_level']),dtype=np.float32)
    background = arr*(1-p['outside_mix'])+background_color*p['outside_mix']
    shifts = p['outline_warp']*unit*(bend+.25*np.sin(y*.017-clock*1.7))
    coverage = _row_sample(mask,shifts) if p['outline_warp'] else mask
    if p['edge_echo']:
        for distance,strength in ((2.,.2),(1.,.4)):
            echo = _row_sample(mask,shifts-distance*p['edge_distance']*unit)
            alpha = echo[...,None]*p['edge_echo']*strength
            background = background*(1-alpha)+signal*alpha
    result = signal*coverage[...,None]+background*(1-coverage[...,None])
    return (arr*(1-p['mix'])+result*p['mix']).astype(np.float32)
