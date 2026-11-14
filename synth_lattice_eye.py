"""Optional engraved eye for the printed lattice, with periodic natural blinks.

Geometry uses the lattice's artwork scale. Eyelids occlude a stationary iris;
the completed drawing passes through the same pigment and finishing stages.
"""
import numpy as np

from synth_lattice_relief import rgb, smooth


def parameters(P):
    return (
        P('eye_enabled', 'Center eye', 0, 0, 1, 1, choices=('Off', 'On')),
        P('eye_size', 'Eye width (cells)', 3.2, 1., 7., .05),
        P('eye_placement', 'Eye placement', 0, 0, 1, 1, 'Leave space removes nearby cells. Overlay figures keeps every cell moving behind the eye, including during blinks. The eye shares the same surface treatment.', choices=('Leave space', 'Overlay figures')),
        P('eye_clearance', 'Space around eye', .18, 0., 1.5, .01, 'Extra space in cell intervals when Eye placement is Leave space. Nearby cells leave room for the eye, including while it blinks.'),
        P('eye_opening', 'Eye opening', 1., 0., 1., .01, 'Resting opening. Zero holds the eyelids closed.'),
        P('eye_iris', 'Iris size', 1., .5, 1.35, .01),
        P('eye_pupil', 'Pupil size', .59, .2, .85, .01, 'Relative to the iris. The iris stays circular while the lids close over it.'),
        P('eye_line', 'Line weight', 1., .5, 2., .05),
        P('eye_hue', 'Eye color hue', .19, 0., 1., .01),
        P('eye_saturation', 'Eye color saturation', .15, 0., 1., .01),
        P('eye_light', 'Eye color brightness', .87, 0., 1., .01),
        P('eye_ink_hue', 'Eye ink hue', .16, 0., 1., .01),
        P('eye_ink_saturation', 'Eye ink saturation', .34, 0., 1., .01),
        P('eye_ink_light', 'Eye ink brightness', .055, 0., 1., .01),
        P('eye_blink_count', 'Blinks per cycle', 2, 0, 12, 1, 'Zero disables automatic blinking; Eye opening remains editable.'),
        P('eye_blink_period', 'Blink cycle (s)', 8., 1., 60., .1, 'Use the clip duration, or a divisor of it, for a seamless repeating blink pattern.'),
        P('eye_blink_duration', 'Blink duration (s)', .38, .12, 1.5, .01, 'Quick closure, brief contact and a slower reopening.'),
        P('eye_blink_fps', 'Blink cadence', 0, 0, 60, 1, 'Zero follows Timeline FPS. Positive values hold eyelid poses at this many frames per second, independently of the cells and texture. Try 6, 8 or 12 for stepped motion. Blink duration and Blinks per cycle control speed and frequency separately.'),
        P('eye_blink_variation', 'Blink irregularity', .75, 0., 1., .01, 'Vary intervals and speed deterministically, so export and random seeking agree.'),
        P('eye_double_blink', 'Double blink amount', .30, 0., 1., .01),
        P('eye_blink_phase', 'Blink phase', 0., 0., 1., .01),
    )


EYE_KEYS = frozenset(('eye_enabled', 'eye_size', 'eye_placement', 'eye_clearance', 'eye_opening',
    'eye_iris', 'eye_pupil', 'eye_line', 'eye_blink_count', 'eye_blink_period',
    'eye_blink_duration', 'eye_blink_fps', 'eye_blink_variation', 'eye_double_blink', 'eye_blink_phase',
    *(name+'_'+channel for name in ('eye', 'eye_ink') for channel in ('hue', 'saturation', 'light'))))


def blink_opening(seconds, p, seed=0):
    """A deterministic circular schedule; no accumulated animation state."""
    count = int(p['eye_blink_count'])
    if not count: return float(p['eye_opening'])
    period = max(.01, p['eye_blink_period'])
    slot = period/count
    rng = np.random.default_rng((int(seed)+0xE1E) % (2**32))
    phase = float(seconds)+p['eye_blink_phase']*period
    fps = p.get('eye_blink_fps', 0)
    if fps:
        # Sample on a cycle-local clock so fractional cycle lengths still loop.
        # The shorter final hold ends at the cycle boundary, not at an unrelated
        # global frame tick. Missing/zero preserves the original continuous path.
        phase = (np.floor((phase % period)*fps+1e-9)/fps) % period
    closure = 0.
    for i in range(count):
        jitter, speed, double = rng.random(3)
        start = (i+.36+(jitter-.5)*.35*p['eye_blink_variation'])*slot
        duration = min(p['eye_blink_duration']*(1+(speed-.5)*.4*p['eye_blink_variation']), slot*.28)
        starts = (start, start+duration*1.35) if double < p['eye_double_blink'] else (start,)
        for event in starts:
            q = ((phase-event) % period)/max(.001, duration)
            if q >= 1: continue
            amount = smooth(q/.24) if q < .24 else 1-smooth((q-.34)/.66)
            closure = max(closure, float(amount))
    return float(p['eye_opening'])*(1-closure)


def reserved_cells(ix, iy, spacing, grid_center, center, p):
    """Remove complete cells, not fragments cut by a rectangular overlay."""
    width = p['eye_size']*spacing
    rx = width*.52+p['eye_clearance']*spacing
    ry = width*.23+p['eye_clearance']*spacing
    x = ix*spacing+grid_center[0]-center[0]
    y = iy*spacing+grid_center[1]-center[1]
    # A cell's footprint may overlap the eye even if its center is outside it.
    return (np.maximum(np.abs(x)-spacing*.4, 0)/rx)**2+(np.maximum(np.abs(y)-spacing*.4, 0)/ry)**2 < 1


def render_eye(result, p, seconds, preset, center, spacing, unit):
    """Composite an almond contour, engraved iris and offset relief highlights."""
    h, w = result.shape[:2]
    width = p['eye_size']*spacing
    cx, cy = center
    left, right = max(0, int(cx-width*.56-3)), min(w, int(cx+width*.56+4))
    top, bottom = max(0, int(cy-width*.34-3)), min(h, int(cy+width*.34+4))
    if right <= left or bottom <= top: return result
    yy, xx = np.mgrid[top:bottom, left:right].astype(np.float32)
    x, y = xx-cx, yy-cy
    u = x/(width*.5)
    arch = np.maximum(0, 1-u*u)**1.15
    opening = blink_opening(float(seconds)*preset.get('speed', 1.), p, preset.get('seed', 0))
    # The open drawing's bounds are centered. Corners stay put during a blink.
    canthus = .0525*width
    closed = canthus+.025*width*arch
    upper = closed+opening*(canthus-.265*width*arch-closed)
    lower = closed+opening*(canthus+.160*width*arch-closed)
    aa = max(.55, .6*unit)
    span = smooth((width*.5-np.abs(x)+aa)/(2*aa))
    lid = smooth((y-upper+aa)/(2*aa))*smooth((lower-y+aa)/(2*aa))*span
    body, ink = rgb(p, 'eye'), rgb(p, 'eye_ink')
    first = rgb(p, 'face_a')
    radius = width*.207*p['eye_iris']
    r = np.hypot(x, y+.014*width)
    theta = np.arctan2(y+.014*width, x)
    iris_mask = smooth((radius-r+aa)/(2*aa))
    tone = body*(.91+.09*np.cos(x/width*3))[..., None]
    tone = np.broadcast_to(tone, (*x.shape,3)).copy()
    iris_color = first*.55+body*.45
    iris_light = .82+.18*smooth(r/radius)
    iris = iris_color*iris_light[..., None]
    # Short, irregular engraved strokes, concentric rims and fine stippling.
    radial = np.sin(theta*53+np.sin(theta*7)*1.2+r/radius*2.5)
    hatching = smooth((radial-.86)/.12)*smooth((r/radius-.62)/.10)*(1-smooth((r/radius-.94)/.04))
    hatching *= .45+.55*smooth(np.sin(theta*11+r/radius*21))
    rim = np.maximum(np.exp(-((r-radius*.98)/max(.6,width*.006*p['eye_line']))**2),
                     np.exp(-((r-radius*.87)/max(.45,width*.003*p['eye_line']))**2)*.8)
    engraving = np.maximum(hatching*.85, rim)
    iris = iris*(1-engraving[...,None])+ink*engraving[...,None]
    tone = tone*(1-iris_mask[...,None])+iris*iris_mask[...,None]
    pupil_radius = radius*p['eye_pupil']
    pupil = smooth((pupil_radius-np.hypot(x, y+.04*width)+aa)/(2*aa))
    tone = tone*(1-pupil[...,None])+ink*pupil[...,None]
    # Highlights are attached to the iris and disappear under the moving lid.
    shine = np.zeros_like(x)
    for hx, hy, hr in ((.36,-.51,.22),(.47,.12,.10),(-.02,.34,.065)):
        dot = smooth((radius*hr-np.hypot(x-radius*hx,y-radius*hy)+aa)/(2*aa))
        shine = np.maximum(shine,dot)
    tone = tone*(1-shine[...,None])+body*shine[...,None]
    # Curved ink strokes: a heavier upper lash, fine lower rim and lid crease.
    upper_slope = np.gradient(upper, axis=1) if upper.shape[1]>1 else np.zeros_like(upper)
    lower_slope = np.gradient(lower, axis=1) if lower.shape[1]>1 else np.zeros_like(lower)
    du = (y-upper)/np.sqrt(1+upper_slope*upper_slope)
    dl = (y-lower)/np.sqrt(1+lower_slope*lower_slope)
    weight = width*.009*p['eye_line']
    upper_ink = smooth((weight*(.6+.65*arch)-np.abs(du)+aa)/(2*aa))*span
    lower_ink = smooth((weight*.52-np.abs(dl)+aa)/(2*aa))*span
    fold = upper-.035*width*arch*opening
    crease = smooth((weight*.4-np.abs((y-fold)/np.sqrt(1+upper_slope*upper_slope))+aa)/(2*aa))*span*opening
    outline = np.maximum(np.maximum(upper_ink,lower_ink),crease)
    alpha = np.maximum(lid,outline)
    tone = tone*(1-outline[...,None])+ink*outline[...,None]
    # Relief follows the same light as neighboring cells, without a flat plate.
    highlight = np.exp(-((du+weight*1.65)/max(.5,unit*.7))**2)*span*arch*opening
    alpha = np.maximum(alpha,highlight*.5)
    tone += (highlight*p['bevel']*.22)[...,None]*body
    shadow = np.exp(-((dl-weight*2)/max(.6,unit*1.2))**2)*span*.3
    tile = result[top:bottom,left:right]
    tile *= 1-shadow[...,None]
    result[top:bottom,left:right] = tile*(1-alpha[...,None])+tone*alpha[...,None]
    return result
