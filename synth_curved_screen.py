"""Project any image and a wire grid onto the same curved, worn surface."""
import math

import numpy as np

from synth_modulation import _field, _noise
from synth_print_paint import _sample


def modules(Module, P):
    return (Module('curved_screen', 'Curved screen',
        'A tilted curved image plane with an editable wire grid and worn dark surface.', (
        P('angle', 'Screen angle', 20., -180, 180, 1),
        P('curve', 'Surface curvature', .35, 0, 1.5, .01),
        P('center_x', 'Curvature center X', .22, -.5, .5, .01),
        P('center_y', 'Curvature center Y', 0., -.5, .5, .01),
        P('scale', 'Screen scale', 1., .25, 3, .01),
        P('spacing', 'Grid spacing', 80., 12, 240, 1, 'Pixels at a 720-pixel reference edge.'),
        P('line_width', 'Grid line width', 1.2, .1, 8, .1),
        P('grid', 'Grid brightness', .16, 0, 1, .01),
        P('grid_fade', 'Grid directional fade', .85, 0, 1, .01, 'Fade the grid toward the left side of the surface.'),
        P('wear', 'Grid wear', .65, 0, 1, .01),
        P('background', 'Surface brightness', .055, 0, 1, .005),
        P('patina', 'Surface patina', .12, 0, .5, .005),
        P('grain', 'Surface grain', .025, 0, .25, .005),
        P('drift', 'Surface drift', .25, 0, 4, .05),
        P('rate', 'Motion speed', .3, 0, 3, .05),
        P('vibration', 'Surface vibration', 0., 0, 12, .1, 'Irregular movement shared by the source and grid, in pixels at a 720-pixel reference edge.'),
        P('flutter', 'Surface flutter', 0., 0, 20, .1, 'Local vibration of the curved surface. Zero keeps the original projection.'),
        P('breathing', 'Curvature motion', 0., 0, .3, .005, 'Subtle continuous variation around the chosen surface curvature.'),
        P('boil', 'Texture movement', 0., 0, 1, .05, 'Evolution of the worn grid and surface texture. Zero keeps their original placement.'),
    )),)


def render_curved_screen(arr, p, time, speed, seed, reference_size):
    h, w = arr.shape[:2]; cw, ch = reference_size
    unit = min(cw, ch) / 720
    y, x = np.mgrid[:h, :w].astype(np.float32)
    clock = time * speed * p['rate']
    angle = math.radians(p['angle'])
    c, s = math.cos(angle), math.sin(angle)
    x = x-w/2; y = y-h/2
    u = (c*x+s*y)/p['scale']; v = (-s*x+c*y)/p['scale']
    u += p['drift']*unit*math.sin(clock*1.7)
    v += p['drift']*unit*math.sin(clock*1.13+1.2)
    if p.get('vibration', 0):
        # Continuous seeded noise avoids a repeated sine-wave shake. It is
        # evaluated from time, so seeking and export have identical motion.
        u += (float(_field(clock*13., 0., seed+31))-.5)*2*p['vibration']*unit
        v += (float(_field(clock*11., 1., seed+33))-.5)*2*p['vibration']*unit
    if p.get('flutter', 0):
        dx = _field(u/(48*unit)+clock*4.1, v/(64*unit)-clock*3.3, seed+35)-.5
        dy = _field(u/(64*unit)-clock*3.7, v/(48*unit)+clock*4.7, seed+37)-.5
        u += dx*(2*p['flutter']*unit)
        v += dy*(2*p['flutter']*unit)
    du, dv = u-p['center_x']*cw, v-p['center_y']*ch
    # The image and grid use this single inverse projection, so their curves
    # remain registered when the canvas, angle or curvature changes.
    curve = p['curve']
    if p.get('breathing', 0):
        curve += p['breathing']*(.62*math.sin(clock*2.9)+.38*math.sin(clock*5.13+1.1))
    bend_x = curve*((du/cw)**2 + 1.4*(dv/ch)**2)
    bend_y = curve*(1.5*(du/cw)**2 + .3*(dv/ch)**2)
    su, sv = u + du*bend_x, v + dv*bend_y
    source = _sample(arr, su+w/2, sv+h/2)
    valid = (su>=-w/2)&(su<w/2)&(sv>=-h/2)&(sv<h/2)
    source *= valid[..., None]
    ux, vy = su/unit, sv/unit
    # Animate the texture coordinates rather than replacing the texture each
    # frame; this retains the worn surface while its details crawl and flicker.
    tx, ty = ux, vy
    if p.get('boil', 0):
        tx = ux + p['boil']*clock*27.
        ty = vy - p['boil']*clock*19.
    rough = (_field(tx/3.5, ty/3.5, seed+3)-.5)*(1.+p['wear']*3.)
    gx = np.abs((ux+rough+p['spacing']/2) % p['spacing'] - p['spacing']/2)
    gy = np.abs((vy+rough+p['spacing']/2) % p['spacing'] - p['spacing']/2)
    distance = np.minimum(gx, gy)
    grid = np.exp(-.5*(distance/max(.5/unit, p['line_width']))**2)
    direction = np.clip((u/cw+.45)*2., .04, 1.)
    broken = np.clip((_field(tx/7., ty/7., seed+5)-.2)*2., 0, 1)
    grid *= p['grid']*(1-p['wear']+p['wear']*broken)*(1-p['grid_fade']+p['grid_fade']*direction)
    cloud = _field(ux/115., vy/115., seed+7)
    fibers = .55*_field(tx/1.4, ty/1.4, seed+9)+.45*_noise(np.floor(tx), np.floor(ty), seed+10)
    left = np.exp(-.5*((u/cw+.25)/.32)**2-.5*((v/ch+.04)/.48)**2)
    patina = np.clip((cloud-.25)*2., 0, 1)*np.clip((fibers-.47)*4., 0, 1)*left
    grain = _noise(np.floor(ux), np.floor(vy), seed+11+int(clock*24))-.5
    surface = np.maximum(0, p['background'] + grid + patina*p['patina'] + grain*p['grain'])
    return np.maximum(source, surface[..., None])
