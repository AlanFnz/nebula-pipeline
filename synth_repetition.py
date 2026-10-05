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
        P('band_flow', 'Band flow', 0., 0, 1, .01, 'Continuously compress, expand and bend groups of rows. Zero keeps the original band layout.'),
        P('sync_loss', 'Sync loss', 0., 0, 1, .01, 'Brief signal unlocks: repetitions stretch, split into color and snap back together.'),
        P('slip_frequency', 'Slip frequency', 1.2, 0, 4, .05, 'Average unlocks per second. Motion speed and the composition speed scale this rate. Timing varies; zero disables unlocks.'),
        P('line_flutter', 'Line flutter', 0., 0, 1, .01, 'Fast, uneven movement of fine scan rows and their colored edges.'),
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


def _sync_envelope(clock, frequency, seed):
    """Irregular fast attacks and slower recoveries, reconstructible on any seek.

    Neighboring event windows overlap the clock boundary so there is no reset
    when moving into the next window. Frequency zero means no unlocks.
    """
    if frequency <= 0: return 0.
    position = clock*frequency
    window = math.floor(position)
    value = 0.
    for event in range(window-1, window+2):
        center = event+.18+.64*float(_noise(event, 0, seed+910))
        age = position-center
        attack = .025+.025*float(_noise(event, 0, seed+911))
        recovery = .13+.21*float(_noise(event, 0, seed+912))
        envelope = float(_smooth(-attack, 0., age))*(1-float(_smooth(0., recovery, age)))
        value = max(value, envelope*(.6+.4*float(_noise(event, 0, seed+913))))
    return value


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
    flow = p.get('band_flow', 0.)
    flutter = p.get('line_flutter', 0.)
    loss = p.get('sync_loss', 0.)
    unlock = loss*_sync_envelope(clock, p.get('slip_frequency', 1.2), seed) if loss else 0.
    alive = bool(flow or flutter or p.get('sync_loss', 0.))
    if flow:
        # Broad moving fields change both the height and slope of the bands.
        # The same clock drives phase, sample position and fringe separation.
        band += flow*(2.8*(_field(y/180, clock*.9, seed+881)-.5)
                      +.65*np.sin(y*.012-clock*2.4)+clock*.23)
    cell = np.floor(band)
    bend = np.sin(band*math.tau+clock*1.3)
    bend = bend*(1-p['row_breakup']) + p['row_breakup']*(2/np.pi*np.arcsin(bend))
    band_phase = (_noise(cell,0,seed+43)-.5)*p['row_breakup']*p['spacing']
    phase = p['wave']*(bend+.35*np.sin(band*3.3-clock*2.1)) + band_phase
    phase += p['instability']*p['spacing']*(_field(band*.6,clock*1.4,seed)-.5)
    phase += clock*p['drift'] + left*p['contour']
    if alive:
        surge = flow*(.4+1.6*_field(y/150, clock*2.1, seed+885))
        phase += p['spacing']*surge*np.sin(y*.019+clock*4.1+np.sin(clock*1.7))
        phase += unlock*p['spacing']*2.4*np.sin(y*.008+clock*3.7)
        phase += flutter*p['spacing']*1.4*(_field(y/3., clock*23, seed+887)-.5)
    scan_row = np.floor(y/2.5)
    phase += (_noise(scan_row,0,seed+321)-.5)*p['spacing']*.16*p['row_lines']
    phase += np.sin(y*.91+clock*2.3)*p['row_lines']*.7
    spacing = p['spacing']*(1+p['row_breakup']*.18*(_noise(cell,0,seed+71)-.5)*2)
    if alive:
        spacing *= (1+flow*.55*np.sin(y*.009+clock*2.3+np.sin(clock*.8)))
        spacing *= 1+unlock*(3.5+2.*np.sin(y*.012-clock*2.))
    cycle = (x[None,:]-phase[:,None])/spacing[:,None]
    # Each cell samples actual source pixels. No procedural pattern is pasted on.
    center = left+(right-left)*p['sample_center']
    if flow:
        center += (right-left)*flow*.12*(_field(y/120,clock*1.7,seed+889)-.5)
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
    if unlock:
        # During an unlock the dense folds briefly resolve into a larger,
        # cyan picture. Different scan groups recover at different times.
        release = np.clip(unlock*1.7*(.65+.7*_field(y/90,clock*1.2,seed+891)),0,1)
        exposed = (.28+luma*.7)[...,None]*cyan
        exposed += (luma-_blur(luma,3*unit))[...,None]*p['relief']*.25
        signal = signal*(1-release[:,None,None])+exposed*release[:,None,None]
    if p['color_slips'] and alive:
        # Short scan-line streaks follow the very same loss of sync that pulls
        # the picture. Avoid independent, solid magenta checkerboard cells.
        streak = _field(x[None,:]/100, y[:,None]/3.+clock*15, seed+893)
        fault = np.clip(_smooth(.53,.8,streak)*(flutter*.55+unlock*1.6)*p['color_slips'],0,.95)
        fault *= .35+.65*np.clip(ridge+unlock,0,1)
        burst = _smooth(.52,.76,_field(y/100,clock*2.7,seed+899))*unlock*p['color_slips']
        fault = np.maximum(fault,burst[:,None]*.95)
        hot = np.array((1.,.12,.28),dtype=np.float32)
        signal = signal*(1-fault[...,None])+hot*tone[...,None]*fault[...,None]
    elif p['color_slips']:
        faults = _noise(np.floor(cycle),cell[:,None],seed+int(math.floor(clock*13))*31)
        fault = _smooth(1-p['color_slips']*.13,1.,faults)[...,None]
        magenta = np.array((.7,.08,.4),dtype=np.float32)
        signal = signal*(1-fault)+tone[...,None]*magenta*fault
    signal *= (.7+.3*sampled[...,1,None])
    if alive:
        signal *= (1+flow*.18*np.sin(y*.027-clock*5.1))[:,None,None]
        signal += unlock*.16*cyan
        if flutter:
            # Fine scan fragments interrupt the repeated contours themselves,
            # before the optical CRT finish softens their edges.
            breakup = _field(x[None,:]/24, y[:,None]/2.5+clock*19, seed+895)
            signal *= (1-flutter*.72*_smooth(.46,.78,breakup))[...,None]
            signal += (flutter*.18*ridge*_smooth(.63,.84,breakup))[...,None]
    interrupted = _smooth(.91,.99,band % 1)*p['row_lines']
    if alive:
        interrupted *= 1-unlock*.85
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
    if alive:
        shifts += unit*p['outline_warp']*(unlock*2*np.sin(y*.015-clock*4.)
                    +flutter*2*(_field(y/4,clock*19,seed+897)-.5))
    coverage = _row_sample(mask,shifts) if p['outline_warp'] else mask
    if p['edge_echo']:
        for distance,strength in ((2.,.2),(1.,.4)):
            echo = _row_sample(mask,shifts-distance*p['edge_distance']*unit*(1+unlock*2))
            alpha = echo[...,None]*p['edge_echo']*strength
            background = background*(1-alpha)+signal*alpha
    result = signal*coverage[...,None]+background*(1-coverage[...,None])
    return (arr*(1-p['mix'])+result*p['mix']).astype(np.float32)
