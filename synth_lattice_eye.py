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
        P('eye_separation', 'Contour gap', 0., 0., 200., .5, 'Background-colored space following the eye outline, including during blinks. In Overlay figures only. Up to 200 pixels at a 720-pixel artwork edge; try 60–100 for a wider margin. Zero restores the original overlay.'),
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
        P('eye_reveal', 'Materialization', 0., 0., 1., .01, 'Granular appearance of cells uncovered by a blink in Overlay figures. Zero keeps the immediate reveal.'),
        P('eye_reveal_duration', 'Reveal duration (s)', .16, .03, .6, .01, 'Time for newly uncovered pigment to become solid, at global speed 1. Independent of held eyelid poses.'),
        P('eye_reveal_grain', 'Reveal grain size', 1.5, .4, 5., .1, 'Pigment particle size in pixels at a 720-pixel artwork edge. Shares the existing print and finishing effects.'),
        P('eye_ripple', 'Ripple amount', 0., 0., 1., .01, 'A subtle circular wave through the cells when the eye closes. Zero disables it. The eye and paper texture stay in place.'),
        P('eye_ripple_response', 'Cell response', 0, 0, 3, 1, 'Custom mix gives independent size, rotation, position and fluid-wave amounts. The first three modes preserve their original response.', choices=('Fluid wave', 'Size pulse', 'Pulse + shake', 'Custom mix')),
        P('eye_ripple_size', 'Size pulse', 100., 0., 100., 1., 'Custom mix: strength of the brief enlargement. 100% matches Size pulse mode; zero leaves cell size unchanged. Dense cells grow less to preserve spacing.'),
        P('eye_ripple_rotation', 'Rotation shake', 0., 0., 20., .1, 'Custom mix: maximum rotation in degrees before Ripple amount and distance attenuation. Each figure briefly rocks around its own center, then returns to its original angle.'),
        P('eye_ripple_position', 'Position shake', 0., 0., 100., 1., 'Custom mix: strength of the small position vibration. 100% matches Pulse + shake; zero keeps each cell center in place.'),
        P('eye_ripple_fluid', 'Fluid wave', 0., 0., 100., 1., 'Custom mix: blend in the original flowing deformation. Try 10–20% for a subtle trace; zero removes it. Ripple amount remains the shared master control.'),
        P('eye_ripple_glow', 'Glow pulse', 0., 0., 200., 1., 'Custom mix: briefly light each figure as the radial signal arrives, using its own color. Zero disables the light pulse. Ripple amount scales it together with the other responses.'),
        P('eye_ripple_glow_radius', 'Glow softness', 6., 1., 24., .5, 'Custom mix: spread of the halo, in pixels at a 720-pixel artwork edge. The eye stays in front of the glowing cells. Ripple width sets pulse duration.'),
        P('eye_ripple_speed', 'Ripple speed', 7., 2., 24., .1, 'Cell intervals per second at global speed 1. The wave starts with each visible blink and moves smoothly, independently of held cell poses.'),
        P('eye_ripple_reach', 'Ripple reach', 10., 2., 20., .1, 'Maximum radius in cell intervals. The wave loses strength as it travels and fades out at this distance.'),
        P('eye_ripple_width', 'Ripple width', .8, .3, 2.5, .05, 'Width of the wave in cell intervals. Larger values make each response last longer.'),
    )


EYE_KEYS = frozenset(('eye_enabled', 'eye_size', 'eye_placement', 'eye_clearance', 'eye_separation', 'eye_opening',
    'eye_iris', 'eye_pupil', 'eye_line', 'eye_blink_count', 'eye_blink_period',
    'eye_blink_duration', 'eye_blink_fps', 'eye_blink_variation', 'eye_double_blink', 'eye_blink_phase',
    'eye_reveal', 'eye_reveal_duration', 'eye_reveal_grain',
    'eye_ripple', 'eye_ripple_response', 'eye_ripple_speed', 'eye_ripple_reach', 'eye_ripple_width',
    'eye_ripple_size', 'eye_ripple_rotation', 'eye_ripple_position', 'eye_ripple_fluid',
    'eye_ripple_glow', 'eye_ripple_glow_radius',
    *(name+'_'+channel for name in ('eye', 'eye_ink') for channel in ('hue', 'saturation', 'light'))))


def blink_events(p, seed=0):
    """Shared deterministic schedule for the lids and their visual responses."""
    count = int(p['eye_blink_count'])
    if not count: return ()
    period = max(.01, p['eye_blink_period'])
    slot = period/count
    rng = np.random.default_rng((int(seed)+0xE1E) % (2**32))
    events = []
    for i in range(count):
        jitter, speed, double = rng.random(3)
        start = (i+.36+(jitter-.5)*.35*p['eye_blink_variation'])*slot
        duration = min(p['eye_blink_duration']*(1+(speed-.5)*.4*p['eye_blink_variation']), slot*.28)
        starts = (start, start+duration*1.35) if double < p['eye_double_blink'] else (start,)
        events.extend((event, duration) for event in starts)
    return tuple(events)


def blink_opening(seconds, p, seed=0):
    """A deterministic circular schedule; no accumulated animation state."""
    if not int(p['eye_blink_count']): return float(p['eye_opening'])
    period = max(.01, p['eye_blink_period'])
    phase = float(seconds)+p['eye_blink_phase']*period
    fps = p.get('eye_blink_fps', 0)
    if fps:
        # Sample on a cycle-local clock so fractional cycle lengths still loop.
        # The shorter final hold ends at the cycle boundary, not at an unrelated
        # global frame tick. Missing/zero preserves the original continuous path.
        phase = (np.floor((phase % period)*fps+1e-9)/fps) % period
    closure = 0.
    for event, duration in blink_events(p, seed):
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


def contour_gap_mask(x, y, width, arch, aa, p, opening, gap):
    """Expand the moving ink silhouette with a rounded, artwork-scaled gap.

    Normal distances keep the margin even along the curved lids. The horizontal
    distance rounds the two tips instead of extending a rectangular cutout.
    This is local to the eye, independent of grid motion and frame history.
    """
    canthus = .0525*width
    closed = canthus+.025*width*arch
    upper = closed+opening*(canthus-.265*width*arch-closed)
    lower = closed+opening*(canthus+.160*width*arch-closed)
    us = np.gradient(upper, axis=1) if x.shape[1] > 1 else np.zeros_like(x)
    ls = np.gradient(lower, axis=1) if x.shape[1] > 1 else np.zeros_like(x)
    un, ln = np.sqrt(1+us*us), np.sqrt(1+ls*ls)
    weight = width*.009*p['eye_line']
    top = (upper-y)/un-weight*(.6+.65*arch)
    # Include the crease when visible, so the gap surrounds the entire drawing.
    if opening > 0:
        fold = upper-.035*width*arch*opening
        top = np.minimum(top, (fold-y)/un-weight*.4*opening)
    bottom = (y-lower)/ln-weight*.52
    dy = np.maximum(top, bottom)
    dx = np.abs(x)-width*.5
    distance = np.hypot(np.maximum(dx, 0), np.maximum(dy, 0))+np.minimum(np.maximum(dx, dy), 0)
    return smooth((gap-distance+aa)/(2*aa))


def materialize_cells(tile, x, y, width, arch, span, aa, p, clock, seed, unit, opening):
    """Reveal only pigment recently uncovered by the lid, without frame history.

    Sample the same periodic blink clock, including its held poses. A stable
    particle field fills in with exposure age instead of flickering each frame.
    The moving lattice remains untouched beneath this short-lived pigment mask.
    """
    amount = p.get('eye_reveal', 0.)
    if (not amount or not p.get('eye_placement', 0) or not p['eye_blink_count']
            or opening >= p['eye_opening']):
        return tile
    duration = p.get('eye_reveal_duration', .16)
    ages = np.linspace(duration/24, duration, 24)
    history = []
    seen = set()
    for age in ages:
        pose = blink_opening(clock-age, p, seed)
        # Older samples of the same held pose cannot add more missing pigment.
        if pose > opening+1e-8 and pose not in seen:
            history.append((age, pose))
            seen.add(pose)
    if not history:
        return tile

    canthus = .0525*width
    closed = canthus+.025*width*arch
    def coverage(pose):
        gap = p.get('eye_separation', 0.)*unit
        if gap:
            return contour_gap_mask(x, y, width, arch, aa, p, pose, gap)
        upper = closed+pose*(canthus-.265*width*arch-closed)
        lower = closed+pose*(canthus+.160*width*arch-closed)
        return smooth((y-upper+aa)/(2*aa))*smooth((lower-y+aa)/(2*aa))*span

    current = coverage(opening)
    grain = max(.2, p.get('eye_reveal_grain', 1.5)*unit)
    # Float64 hashing keeps the same artwork-space field at preview/export sizes.
    gx = np.floor(x.astype(np.float64)/grain)
    gy = np.floor(y.astype(np.float64)/grain)
    noise = np.mod(np.sin(gx*127.1+gy*311.7+(int(seed) % 65536)*.123)*43758.5453, 1.)
    missing = np.zeros_like(x)
    for age, pose in history:
        progress = age/duration
        pigment = smooth((progress*1.2-noise)/.2)
        uncovered = np.maximum(coverage(pose)-current, 0.)
        missing = np.maximum(missing, uncovered*(1-pigment))
    missing *= amount
    paper = rgb(p, 'paper')
    return tile*(1-missing[..., None])+paper*missing[..., None]


def render_eye(result, p, seconds, preset, center, spacing, unit):
    """Composite an almond contour, engraved iris and offset relief highlights."""
    h, w = result.shape[:2]
    width = p['eye_size']*spacing
    gap = p.get('eye_separation', 0.)*unit if p.get('eye_placement', 0) else 0.
    cx, cy = center
    left, right = max(0, int(cx-width*.56-gap-3)), min(w, int(cx+width*.56+gap+4))
    top, bottom = max(0, int(cy-width*.34-gap-3)), min(h, int(cy+width*.34+gap+4))
    if right <= left or bottom <= top: return result
    yy, xx = np.mgrid[top:bottom, left:right].astype(np.float32)
    x, y = xx-cx, yy-cy
    u = x/(width*.5)
    arch = np.maximum(0, 1-u*u)**1.15
    clock = float(seconds)*preset.get('speed', 1.)
    seed = preset.get('seed', 0)
    opening = blink_opening(clock, p, seed)
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
    tile = materialize_cells(tile, x, y, width, arch, span, aa, p, clock, seed, unit, opening)
    if gap:
        separation = contour_gap_mask(x, y, width, arch, aa, p, opening, gap)[...,None]
        tile = tile*(1-separation)+rgb(p, 'paper')*separation
    tile *= 1-shadow[...,None]
    result[top:bottom,left:right] = tile*(1-alpha[...,None])+tone*alpha[...,None]
    return result
