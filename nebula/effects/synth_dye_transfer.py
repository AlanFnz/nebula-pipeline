"""Deterministic dye-transfer printing of arbitrary source pixels.

Wording and cuts belong to compositions. No reference frames, typography or
study-specific time switches are used in this image treatment.
"""
import colorsys
import math

import numpy as np
from PIL import Image, ImageFilter
from nebula.effects.synth_print import _fresh_noise, _rng, _scan_paper, _stock_lattice
from nebula.effects.synth_print import paper_grain_controls, paper_grain_field


MASK_TARGETS = ((), ('ink',), ('paper',), ('ink', 'paper'))


def modules(Module, P):
    return (Module('dye_transfer', 'Dye transfer',
        'Saturated film stock, dark or pale impressions, vertical exposure drag and uneven registration.', (
        P('paper_hue', 'Stock hue', .014, 0, 1, .01),
        P('paper_saturation', 'Stock saturation', 1., 0, 1, .01),
        P('paper_light', 'Stock brightness', 1., 0, 1.2, .01),
        P('ink_hue', 'Ink hue', .015, 0, 1, .01),
        P('ink_saturation', 'Ink saturation', .75, 0, 1, .01),
        P('ink_light', 'Ink brightness', .075, 0, 1, .01),
        P('ink_density', 'Ink density variation', 0., 0, 1, .01, 'Uneven pigment density across the impression, leaving the stock unchanged.'),
        P('ink_veil', 'Light through ink', 0., 0, 1, .01, 'Strength of the local exposure through the source ink. Choose its behavior with Light through ink mode.'),
        P('ink_veil_mode', 'Light through ink mode', 0, 0, 1, 1, 'Stock tint adds a colored exposure. Reveal underprint thins ink where it crosses a second paper color, or over the stock on a single-color print.', choices=('Stock tint', 'Reveal underprint')),
        P('ink_veil_x', 'Light position', .25, -1, 1, .01, 'Horizontal position relative to canvas width; zero is the center.'),
        P('ink_veil_y', 'Light position Y', .07, -1, 1, .01, 'Vertical position relative to canvas height. Zero is the center.'),
        P('ink_veil_width', 'Light width', .30, .02, 1, .01, 'Width of the soft exposure relative to canvas width.'),
        P('tooth', 'Printed edge texture', 0., 0, 3, .05, 'Fine irregularities along the ink edge. Pixels at a 720-pixel canvas width.'),
        P('stock_relief', 'Paper relief', 0., 0, 1, .01, 'Side lighting reveals the tooth of the sheet across the paper and both impressions.'),
        *paper_grain_controls(P),
        P('fiber_size', 'Paper tooth size', 1.5, .4, 8, .05, 'Width of the fine paper texture in pixels at a 720-pixel artwork width.'),
        P('dry_ink', 'Source ink breakup', 0., 0, 1, .01, 'Uneven pickup by the source impression lets the color underneath show through.'),
        P('wash', 'Uneven exposure', .14, 0, 1, .01),
        P('halo', 'Exposure halo', 0., 0, 2, .05, 'Light spills around the impression, leaving its ink center dark.'),
        P('dye', 'Edge dye', .32, 0, 1, .01),
        P('edge_leak', 'Edge exposure', 0., 0, 1, .01, 'Colored exposure leaking into the stock. Zero retains the original print.'),
        P('edge_leak_hue', 'Edge exposure hue', .015, 0, 1, .01),
        P('edge_leak_light', 'Edge exposure brightness', 1., 0, 1, .01, 'Brightness of the tint relative to the stock. Lower it to shade a corner of the sheet.'),
        P('edge_leak_angle', 'Edge exposure angle', 0., -180, 180, 1., 'Rotate the exposure across the artwork. At zero the band is vertical.'),
        P('edge_leak_width', 'Edge exposure width', .08, .005, .5, .005),
        P('edge_leak_x', 'Edge exposure position', 0., -1, 2, .01),
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
        P('cadence', 'Print cadence', 15., 0, 60, 1, 'Impressions per second. Zero holds the same grain and registration.'),
        # Opt-in optical finish: zero retains the original printing contract.
        P('emulsion', 'Mottled emulsion', 0., 0, 1, .01, 'Unequal film density and coarse, fine and rubbed stock texture.'),
        P('streaks', 'Exposure streaks', 0., 0, 1, .01, 'Irregular vertical density bands in both the stock and the impression.'),
        P('edge_bloom', 'Edge bloom', 0., 0, 1, .01, 'A narrow light rim around the ink, as in an overexposed print.'),
        P('registration', 'Local registration', 0., 0, 1, .01, 'Small uneven bends and offsets within the impression, without moving the entire picture.'),
        P('focus_flutter', 'Focus flutter', 0., 0, 6, .1, 'Irregular changes in optical focus. Pixels at a 720-pixel canvas width.'),
        P('shutter', 'Shutter pull', 0., -1, 1, .01, 'Drag parts of the impression vertically during a cut. Negative pulls upward; positive pulls downward. Zero keeps it still.'),
        P('mask_shape', 'Mask shape', 0, 0, 6, 1, 'Choose the area of the print to change. Stepped rectangle cuts a notch out of each corner.', choices=('Off', 'Disc', 'Wedge', 'Bulb', 'Rectangle', 'Straight cut', 'Stepped rectangle')),
        P('mask_target', 'Apply mask to', 0, 0, 3, 1, 'Darken print adds an optical shadow. Choose Ink, Paper or both to use a second color inside the mask.', choices=('Darken print', 'Ink', 'Paper', 'Ink and paper')),
        P('mask_size', 'Mask height', 1., .01, 4, .01, 'Height relative to the artwork. For Bulb, sets the round base diameter.'),
        P('mask_aspect', 'Mask width / height', 1., .1, 4, .01, 'Width relative to height. One keeps a disc circular and a rectangle square.'),
        P('mask_x', 'Mask X', 0., -2, 2, .01, 'Horizontal position in artwork widths. Zero is centered.'),
        P('mask_y', 'Mask Y', 0., -2, 2, .01, 'Vertical position in artwork heights. Zero is centered.'),
        P('mask_angle', 'Mask angle', 0., -180, 180, .1),
        P('mask_inset_x', 'Corner cut width', .18, 0, .95, .005, 'Width removed at each corner as a fraction of half the rectangle width.'),
        P('mask_inset_y', 'Corner cut height', .18, 0, .95, .005, 'Height removed at each corner as a fraction of half the rectangle height.'),
        P('mask_softness', 'Mask softness', 2., 0, 160, .5, 'Edge softness in pixels at a 720-pixel artwork width.'),
        P('mask_opacity', 'Mask opacity', 1., 0, 1, .01, 'Blend the masked area with the original print.'),
        P('mask_irregularity', 'Mask edge irregularity', 0., 0, 40, .25, 'Deviation from a straight or smooth cut, in pixels at a 720-pixel artwork width. The edge moves with the mask.'),
        P('mask_dry_ink', 'Second plate breakup', 0., 0, 1, .01, 'Vary the pigment and leave small openings in the colored plate. The sheet stays continuous underneath.'),
        P('mask_grain_size', 'Plate grain size', 0., 0., 12., .1, 'Zero uses the paper tooth size. Set a size in pixels at a 720-pixel artwork width to change this plate independently.'),
        P('mask_density_ramp', 'Plate density gradient', 0., -1, 1, .01, 'Positive values lay down a denser color toward the bottom of the mask. Rotate the mask to turn the gradient.'),
        P('mask_ink_hue', 'Second ink hue', .145, 0, 1, .01),
        P('mask_ink_saturation', 'Second ink saturation', .10, 0, 1, .01),
        P('mask_ink_light', 'Second ink brightness', .98, 0, 1, .01),
        P('mask_paper_hue', 'Second paper hue', .64, 0, 1, .01),
        P('mask_paper_saturation', 'Second paper saturation', .90, 0, 1, .01),
        P('mask_paper_light', 'Second paper brightness', .86, 0, 1.2, .01),
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


def _print_mask(xx, yy, p, reference, offset, seed, tooth=None):
    """Evaluate the mask in artwork space, including its edge outside the canvas.

    Signed edge distances avoid clipping a mask before blurring or allocating
    huge intermediate images when a large silhouette crosses the film gate.
    """
    h, w = xx.shape
    cw, ch = reference
    radius = max(.01, p.get('mask_size', 1.)*ch/2)
    aspect = max(.1, p.get('mask_aspect', 1.))
    a = math.radians(p.get('mask_angle', 0.)); c, s = math.cos(a), math.sin(a)
    x = xx-w/2-(p.get('mask_x', 0.)+offset[0])*cw
    y = yy-h/2-(p.get('mask_y', 0.)+offset[1])*ch
    local_x = c*x+s*y
    local_y = -s*x+c*y
    shape = int(p['mask_shape'])
    if shape in (4, 6):
        edge_x = np.abs(local_x) - radius*aspect
        edge_y = np.abs(local_y) - radius
        edge = np.maximum(edge_x, edge_y)
        if shape == 6:
            corner = np.minimum(edge_x + radius*aspect*p['mask_inset_x'],
                                edge_y + radius*p['mask_inset_y'])
            edge = np.maximum(edge, corner)
    elif shape == 5:
        edge = local_y
    else:
        u = local_x/(radius*aspect)
        v = local_y/radius
        if shape == 2:
            # Triangle with its apex at -1 and its horizontal base at +1.
            distance = np.maximum((np.abs(u)-(v+1)*.5)/math.sqrt(1.25), v-1)
        else:
            distance = np.hypot(u, v)-1
            if shape == 3:
                # Rounded base with a flared neck; union has no internal seam.
                neck = np.maximum.reduce(((np.abs(u)-(.82+(-v-.57)*.5))/math.sqrt(1.25),
                                          v+.57, -1.8-v))
                distance = np.minimum(distance, neck)
        edge = distance*radius*min(1., aspect)
    if p.get('mask_irregularity', 0):
        unit = cw / 720
        x, y = local_x / unit, local_y / unit
        phase = math.tau * (seed % 271) / 271
        contour = (.58*np.sin(.051*x + .063*y + phase + np.sin(.037*y))
                   + .27*np.sin(.132*x - .097*y - phase) + .15*np.sin(.57*x + .41*y + phase))
        edge = edge + p['mask_irregularity']*unit*contour
    if tooth is not None:
        edge += tooth * p['mask_dry_ink'] * cw/720 * 1.4
    # A logistic optical spread supports both crisp discs and defocused ghosts.
    softness = max(.35, p.get('mask_softness', 2.)*cw/720)
    mask = 1/(1+np.exp(np.clip(edge/softness, -60, 60)))
    density = None
    if p.get('mask_density_ramp', 0.):
        # Optical densities add in a print. In RGB reflectance this becomes
        # a power curve; the center retains the selected second color.
        depth = np.clip(local_y / (ch/2 if shape == 5 else radius), -1., 1.)
        density = np.exp2(depth * p['mask_density_ramp'])[..., None]
    return (mask.astype(np.float32)*np.clip(p.get('mask_opacity', 1.), 0, 1))[..., None], density


def deposited_plate(xx, yy, p, reference, offset, seed, frame, dry, *, sheet_relief=None):
    """Coverage and pigment variation for one printed plate."""
    h, w = xx.shape
    unit = reference[0] / 720
    tooth_size = p.get('fiber_size', 1.5) * unit
    grain_size = p.get('mask_grain_size', 0.) * unit or tooth_size
    relief = sheet_relief if grain_size == tooth_size else None
    if dry and relief is None:
        relief = _paper_relief(seed, w, h, grain_size)
    alpha, density = _print_mask(xx, yy, p, reference, offset, seed, relief if dry else None)
    grain = None
    if dry:
        grain, loss = _ink_deposit(_rng(seed, 367, frame), w, h, grain_size, relief)
        alpha *= 1. - dry * loss[..., None]
    return alpha, density, grain


def _print_color(p, material, mask, *, density=None, saturation_gain=1., light_gain=None):
    def color(prefix):
        saturation = min(1., p[prefix + '_saturation'] * saturation_gain)
        light = p[prefix + '_light']
        if light_gain is not None:
            light = min(1., light * light_gain)
        return np.array(colorsys.hsv_to_rgb(p[prefix + '_hue'], saturation, light), np.float32)

    base = color(material)
    if mask is None:
        return base
    second = color('mask_' + material)
    if density is not None:
        second = np.power(second, density)
    return base + mask * (second - base)


def _paper_relief(seed, w, h, size):
    # Illuminate long slanted fibers and the finer pressed tooth of one sheet.
    # Affine sampling keeps even the diagonal ends inside the seeded lattice.
    fine = _scan_paper(seed, w, h, max(.65, size), 0, 0, 0, 1)
    width, length = max(.65, size * .8), max(2., size * 7.)
    shear = .46
    lattice = _stock_lattice(seed, math.ceil((w + shear*h) / width) + 4,
                             math.ceil(h / length) + 4, 37)
    matrix = (1/width, shear/width, 2., 0., 1/length, 2.)
    fiber = np.asarray(lattice.transform((w, h), Image.Transform.AFFINE, matrix, Image.Resampling.BICUBIC))
    return (fine - .5) * 2.9 + (fiber - .5) * 1.6


def _ink_deposit(rng, w, h, size, relief):
    pigment = _fresh_noise(rng, w, h, max(.75, size * 1.2), max(.8, size * 1.6))
    clusters = _fresh_noise(rng, w, h, max(2., size * 4.), max(2., size * 5.))
    pressure = _fresh_noise(rng, w, h, max(4., size * 18.), max(4., size * 23.))
    pickup = .72*pigment + .34*clusters + .25*pressure + .38*relief
    # Most of the plate is covered; only the high tail exposes larger pores.
    loss = np.clip(.028 + .043*pickup + .22*np.maximum(pickup - 1.25, 0.)**2, 0., .95)
    return .84*pigment + .46*pressure, loss


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
        optical_clock = frame/p['cadence'] if p['cadence'] else 0.
        density, streak, rubbed, speckle = _density((w,h), reference, seed, optical_clock)
    a=math.radians(p['angle']); c,s=math.cos(a),math.sin(a)
    dx,dy=rng.normal(0,p['weave'],2)
    gate_offset = (dx, dy)
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
    if p.get('tooth', 0):
        amount = p['tooth']*unit
        ink = _sample(ink, xx+fine*amount, yy+np.roll(fine, 1, axis=1)*amount).astype(np.float32)
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
    mask = plate_density = None
    targets = MASK_TARGETS[int(p.get('mask_target', 0))]
    active_mask = p.get('mask_shape', 0) and p.get('mask_opacity', 1.) > 0
    second_dry = p.get('mask_dry_ink', 0.) if active_mask and targets else 0.
    dry = p.get('dry_ink', 0.)
    relief_strength = p.get('stock_relief', 0.)
    relief = None
    if relief_strength or dry:
        tooth_size = p['fiber_size'] * unit
        relief = _paper_relief(seed, w, h, tooth_size)
    if active_mask:
        mask, plate_density, second_grain = deposited_plate(
            xx, yy, p, reference, gate_offset, seed, frame, second_dry, sheet_relief=relief)
    ink_mask = mask if 'ink' in targets else None
    paper_mask = mask if 'paper' in targets else None
    paper = _print_color(p, 'paper', paper_mask, density=plate_density)
    pigment = _print_color(p, 'ink', ink_mask, density=plate_density)
    if p.get('ink_density', 0):
        thinning = np.clip((cloud*.7+columns*.3-.46)*5, 0, 1)*p['ink_density']
        faded = _print_color(p, 'ink', ink_mask, density=plate_density, light_gain=4)
        pigment = pigment+(faded-pigment)*thinning[...,None]
    if p.get('ink_veil', 0):
        # Continuous optical bands, not thresholded pigment noise. Keep the
        # color in the ink, so changes never recolor the exposed paper itself.
        width = max(.02, p.get('ink_veil_width', .30))
        phase = (seed % 997)*.013
        center = p.get('ink_veil_x', .25) + width*.06*np.sin(ny*4.1+phase)
        vertical = np.exp(-((ny-p.get('ink_veil_y', .07))/.34)**2)
        broad = np.exp(-((nx-center)/width)**2)
        narrow = np.exp(-((nx-center+width*1.45)/(width*.20))**2)*.28
        if p.get('ink_veil_mode', 0):
            veil = np.clip(broad+narrow, 0, 1)*vertical*p['ink_veil']
            if p.get('mask_shape', 0) and 'paper' in targets:
                veil *= paper_mask[..., 0] if paper_mask is not None else 0.
            impression = impression * (1 - veil)
        else:
            veil = np.clip(broad*(.5+.5*vertical)+narrow, 0, 1)*p['ink_veil']
            tint = _print_color(p, 'paper', paper_mask if ink_mask is not None else None,
                                density=plate_density, saturation_gain=1.4, light_gain=.9)
            pigment = pigment+(tint-pigment)*veil[...,None]
    exposure=.8*(cloud-.5)+.2*(columns-.5)
    stock=np.broadcast_to(paper,(h,w,3)).copy()
    if p.get('paper_grain'):
        exposed_grain = paper_grain_field(p, seed, (w, h), cw)
        stock += exposed_grain if paper_mask is None else exposed_grain * (1. - paper_mask)
    if p.get('edge_leak', 0):
        width = p.get('edge_leak_width', .08)
        center = p.get('edge_leak_x', 0.) + (cloud-.5)*width*.22
        axis = nx
        if p.get('edge_leak_angle', 0.):
            angle = math.radians(p['edge_leak_angle'])
            axis = nx*math.cos(angle) + ((yy-h/2)/cw)*math.sin(angle)
        exposure_band = np.exp(-((axis+.5-center)/width)**2)*p['edge_leak']
        tint = np.array(colorsys.hsv_to_rgb(p.get('edge_leak_hue', .015), .98,
                        p['paper_light'] * p.get('edge_leak_light', 1.)), np.float32)
        stock = stock*(1-exposure_band[...,None])+tint*exposure_band[...,None]
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
    if second_dry:
        second_speckle = (second_grain * second_dry * .056)[..., None] * mask
        if paper_mask is not None:
            stock += second_speckle
        if ink_mask is not None:
            pigment = pigment + second_speckle
    if dry:
        source_grain, loss = _ink_deposit(_rng(seed, 369, frame), w, h, tooth_size, relief)
        impression = impression * (1. - dry * loss)
        pigment = pigment + (source_grain * dry * .036)[..., None]
    result=stock*(1-impression[...,None])+pigment*impression[...,None]
    if relief_strength:
        result += (relief * relief_strength * .055)[..., None]
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
    if mask is not None and not targets:
        result *= 1-mask
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
