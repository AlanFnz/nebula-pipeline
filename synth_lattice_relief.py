"""Printed relief for Chromatic lattice, opt-in and independent of frame history.

The cells share the lattice's artwork coordinates. Size follows an angular
sweep; color follows a counter-rotating spiral through the same fixed grid.
"""
import colorsys
import numpy as np


def parameters(P):
    return (
        P('surface', 'Cell surface', 0, 0, 1, 1, choices=('Optical light', 'Printed relief')),
        P('sweep_direction', 'Size sweep direction', 0, 0, 1, 1, choices=('Clockwise', 'Counterclockwise')),
        P('color_direction', 'Color sweep direction', 1, 0, 1, 1, choices=('Clockwise', 'Counterclockwise')),
        P('cadence', 'Motion cadence (fps)', 12., 0, 60, 1, 'Held poses per second. Zero gives continuous motion; Print surface has its own texture cadence.'),
        P('morph', 'Round small cells', 1., 0, 1, .01, 'Blend small cells toward circles as they shrink. Zero keeps the chosen shape throughout.'),
        P('corner', 'Corner rounding', .16, 0, 1, .01),
        P('hollow', 'Hollow transition', 1., 0, 1, .01, 'Open a hollow outline between colors, then grow the next color inside it.'),
        P('bevel', 'Relief depth', .8, 0, 2, .01),
        P('edge_width', 'Bevel width', 4., .5, 12, .1, 'Pixels at a 720-pixel artwork edge.'),
        P('grid_x', 'Grid offset X', 0., -.5, .5, .01, 'Offset in cell intervals; Object position moves the complete artwork.'),
        P('grid_y', 'Grid offset Y', 0., -.5, .5, .01),
        P('face_a_hue', 'First color hue', .39, 0, 1, .01),
        P('face_a_saturation', 'First color saturation', .46, 0, 1, .01),
        P('face_a_light', 'First color brightness', .64, 0, 1, .01),
        P('face_b_hue', 'Second color hue', .87, 0, 1, .01),
        P('face_b_saturation', 'Second color saturation', .56, 0, 1, .01),
        P('face_b_light', 'Second color brightness', .97, 0, 1, .01),
        P('paper_hue', 'Background hue', .16, 0, 1, .01),
        P('paper_saturation', 'Background saturation', .24, 0, 1, .01),
        P('paper_light', 'Background brightness', .145, 0, 1, .01),
    )


RELIEF_KEYS = frozenset(('surface', 'sweep_direction', 'color_direction', 'cadence', 'morph',
    'corner', 'hollow', 'bevel', 'edge_width', 'grid_x', 'grid_y',
    *(f'{name}_{channel}' for name in ('face_a', 'face_b', 'paper')
      for channel in ('hue', 'saturation', 'light'))))


def smooth(x):
    x = np.clip(x, 0, 1)
    return x*x*(3-2*x)


def sweep_size(x, y, seconds, p):
    direction = 1 if p['sweep_direction'] == 0 else -1
    angle = np.arctan2(y, x) - np.deg2rad(p['angle'])
    phase = direction*seconds/p['period'] + p['phase']
    wave = smooth(.5 + .66*np.cos(angle - phase*2*np.pi))
    return 1-p['pulse'] + p['pulse']*(p['minimum']+(1-p['minimum'])*wave)


def color_phase(x, y, seconds, p):
    direction = 1 if p['color_direction'] == 0 else -1
    angle = np.arctan2(y, x) - np.deg2rad(p['angle'])
    return np.sin(p['color_spread']*np.hypot(x, y) - angle
                  + direction*2*np.pi*seconds/p['color_period'] + p['color_phase']*2*np.pi)


def distance(x, y, radius, rounding, shape, sides):
    """Signed distance with a common diameter, including degenerate interiors."""
    radius = np.maximum(radius, .001)
    if shape == 0:
        return np.hypot(x, y)-radius
    if shape == 2:
        x, y = (x+y)*.70710678, (y-x)*.70710678
        radius = radius*.70710678
    if shape in (1, 2):
        corner = radius*np.clip(rounding, 0, 1)
        a = np.abs(x)-radius+corner; b = np.abs(y)-radius+corner
        return np.hypot(np.maximum(a, 0), np.maximum(b, 0)) + np.minimum(np.maximum(a, b), 0)-corner
    sector = 2*np.pi/sides
    theta = np.arctan2(y, x)+np.pi/2
    polygon = np.hypot(x, y)*np.cos((theta+sector/2)%sector-sector/2)/np.cos(np.pi/sides)-radius
    return polygon*(1-rounding) + (np.hypot(x, y)-radius)*rounding


def rgb(p, prefix):
    return np.array(colorsys.hsv_to_rgb(*(p[prefix+'_'+c] for c in ('hue', 'saturation', 'light'))), np.float32)


def render_relief(arr, p, seconds, preset):
    from synth_lattice import lattice_frame, wave_distance, pulse_size, _blur
    h, w = arr.shape[:2]
    center, spacing, unit = lattice_frame(p, (w, h), preset)
    cx = center[0]+p['grid_x']*spacing; cy = center[1]+p['grid_y']*spacing
    cadence = p['cadence']
    t = float(seconds)*preset.get('speed', 1.)
    if cadence: t = np.floor(t*cadence+1e-9)/cadence
    a, b, paper = rgb(p, 'face_a'), rgb(p, 'face_b'), rgb(p, 'paper')
    result = np.empty_like(arr, dtype=np.float32)
    rotation = np.deg2rad(p['rotation']); cs, sn = np.cos(rotation), np.sin(rotation)
    edge_width = max(.25, p['edge_width']*unit)
    ripple = None
    if p.get('eye_ripple', 0.) and p.get('eye_enabled', 0):
        from synth_lattice_eye_ripple import ripple_profile, ripple_coordinates, ripple_cells
        ripple = ripple_profile(p, float(seconds)*preset.get('speed', 1.), preset.get('seed', 0))
    cell_response = bool(p.get('eye_ripple_response', 0))
    fluid = None
    if ripple is not None:
        if not cell_response: fluid = ripple
        elif p['eye_ripple_response'] == 3 and p.get('eye_ripple_fluid', 0.):
            fluid = (ripple[0], ripple[3])
    for top in range(0, h, 128):
        y, x = np.mgrid[top:min(h, top+128), :w].astype(np.float32)
        sample_x, sample_y = ripple_coordinates(x, y, center, spacing, fluid) if fluid is not None else (x, y)
        gx = (sample_x-cx)/spacing; gy = (sample_y-cy)/spacing
        ix = np.floor(gx+.5); iy = np.floor(gy)+.5
        wave = (sweep_size(ix, iy, t, p) if p['wave_shape'] == 3 else
                pulse_size(wave_distance(ix, iy, p), t, p))
        radius = .5*spacing*p['size']*wave
        u = (gx-ix)*spacing; v = (gy-iy)*spacing
        small = np.clip((1-wave)/max(.001, 1-p['minimum']), 0, 1)*p['morph']
        rounding = p['corner']+(1-p['corner'])*small
        if ripple is not None and cell_response:
            u, v, radius = ripple_cells(ix, iy, u, v, radius, rounding, spacing, p, ripple)
        u, v = u*cs+v*sn, -u*sn+v*cs
        sdf = lambda r: distance(u, v, r, rounding, int(p['shape']), int(p['sides']))
        outer = sdf(radius)
        q = color_phase(ix, iy, t, p)
        # The first face recedes into its perimeter, the second grows inside it.
        hole_radius = np.maximum(0, radius-edge_width*1.15)*(1-smooth((q-.03)/.45))*p['hollow']
        hole = sdf(hole_radius)
        incoming_radius = radius*smooth((-q-.015)/.50)
        incoming = sdf(incoming_radius)
        face_mask = np.clip(.5-outer, 0, 1)*(1-np.clip(.5-hole, 0, 1)*(hole_radius>.3))
        next_mask = np.clip(.5-incoming, 0, 1)*(incoming_radius>.3)
        next_mask = np.maximum(next_mask, np.clip(.5-outer, 0, 1)*(q<0)*(1-p['hollow']))
        # Powdery pigment and concave/convex bevels use the same shape distances.
        border = np.minimum(np.abs(outer), np.where(hole_radius>.3, np.abs(hole), 1e6))
        rounded_light = smooth(border/(edge_width*2.3))
        white = np.array((.87, .89, .77), np.float32)
        face_light = .45+.22*np.sin(np.pi*np.clip(q,0,1))
        face = a*.79 + (white-a*.79)*(rounded_light*face_light*p['gradient']/.8)[..., None]
        face *= (.91+.09*np.cos(u/np.maximum(radius, .1)*2.4))[..., None]
        normal = np.clip(.5+.55*(u+v)/np.maximum(np.hypot(u,v),.1),0,1)
        bevel = np.exp(-((border-.65*unit)/max(.4,.6*unit))**2)*p['bevel']
        face += (bevel*(.15+.85*normal))[..., None]*np.array((.55,.55,.48),np.float32)
        fade = smooth(-q/.55)
        violet = np.array(colorsys.hsv_to_rgb((p['face_b_hue']-.13)%1.,p['face_b_saturation'],p['face_b_light']*.75),np.float32)
        inside = smooth(-incoming/(edge_width*2.25))*fade
        next_color = violet+(b-violet)*inside[...,None]
        next_bevel = np.exp(-((np.abs(incoming)-.5*unit)/max(.4,.65*unit))**2)*p['bevel']
        next_color += (next_bevel*(.15+.85*normal))[...,None]*np.array((.4,.46,.34),np.float32)
        # A thin offset edge remains visible while the center is hollow.
        rim = np.exp(-((outer-.3*unit)/max(.4,.65*unit))**2)*p['rim']*(.12+.88*normal)*(radius>.01)
        shadow = np.exp(-((outer-1.3*unit)/max(.5, 1.6*unit))**2)*.30
        tile = np.broadcast_to(paper, (*x.shape, 3)).copy()*(1-shadow[..., None])
        tile = tile*(1-face_mask[..., None])+face*face_mask[..., None]
        tile = tile*(1-next_mask[..., None])+next_color*next_mask[..., None]
        tile += rim[..., None]*np.array((.48, .50, .39), np.float32)
        if p.get('eye_enabled', 0) and not p.get('eye_placement', 0):
            from synth_lattice_eye import reserved_cells
            reserved = reserved_cells(ix, iy, spacing, (cx, cy), center, p)
            tile[reserved] = paper
        result[top:top+128] = tile
    if p.get('eye_enabled', 0):
        from synth_lattice_eye import render_eye
        result = render_eye(result, p, seconds, preset, center, spacing, unit)
    if p['grain']:
        from synth_print import _paper_noise
        tooth = (_paper_noise(int(preset['seed']), w, h, max(.65, unit), 0)-.5)*3.5
        pigment = (_paper_noise(int(preset['seed'])+71, w, h, max(1., unit*2.5), 0)-.5)*3.5
        value = result.max(-1)
        green = smooth((result[...,1]-result[...,0]+.03)*10)
        strength = .025+smooth((value-.18)/.5)*(.20+.80*green)
        result += ((tooth*.8+pigment*.6)*p['grain']*strength)[..., None]
    if p['softness']: result = _blur(result, p['softness']*unit)
    if p['glow']: result += _blur(np.maximum(result-paper, 0), p['glow_radius']*unit)*p['glow']
    lum = result @ np.array((.2126, .7152, .0722), np.float32)
    result = (lum[..., None]+(result-lum[..., None])*p['saturation'])*p['light']
    return np.asarray(arr*(1-p['mix'])+np.clip(result, 0, 1)*p['mix'], np.float32)
