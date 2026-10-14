"""Moving color planes and a separate reusable filmed-emulsion finish.

All animation is sampled from absolute time. Geometry uses a shared reference
scale; expanding the canvas reveals the field without stretching the subject.
"""
import math

import numpy as np
from PIL import Image, ImageFilter

from synth_canvas import content_size, object_offset


def modules(Module, P):
    return (
        Module('prismatic_field', 'Prismatic field',
               'Crossed color planes fold into a polygon, over a drifting optical color field.', (
            P('size', 'Scale', 1., .15, 3, .01),
            P('shape', 'Final shape', 0, 0, 6, 1, 'Shape formed when Gather into shape reaches one. Custom polygon uses Polygon sides.', choices=('Custom polygon', 'Triangle', 'Square', 'Diamond', 'Pentagon', 'Hexagon', 'Circle')),
            P('sides', 'Polygon sides', 3, 3, 8, 1),
            P('center_shape', 'Final placement', 0, 0, 1, 1, 'Canvas center centers the closed shape as the planes gather. Object X/Y still adds your chosen offset.', choices=('Keep hinge position', 'Canvas center')),
            P('gather', 'Gather into shape', 0., 0, 1, .01, 'Zero opens the planes beyond the canvas; one gathers them into a closed polygon.'),
            P('opening', 'Plane opening', .48, .01, 1.5, .01, 'Width of the opposing wedges at their hinge.'),
            P('fold_depth', 'Fold depth', .9, 0, 1, .01, 'How far the planes close toward a thin edge during each cycle.'),
            P('fold_period', 'Fold cycle', 5.8, .2, 30, .1),
            P('fold_phase', 'Fold phase', .1, 0, 1, .01),
            P('rotation', 'Starting angle', 28., -1440, 1440, 1),
            P('rotation_speed', 'Turn speed', 12., -120, 120, .5, 'Degrees per second, before Turn variation.'),
            P('turn_variation', 'Turn variation', .65, 0, 1, .01, 'Accelerate and slow the rotation without reversing its direction.'),
            P('transition_ease', 'Transition easing', 0., 0, 1, .01, 'Give authored turns and folds a stronger acceleration and a longer landing. Zero keeps the original transition curve.'),
            P('turn_settle', 'Turn settle', 0., 0, 1, .01, 'Let an authored turn slightly pass its target, then settle back. Does not affect the color or grain.'),
            P('drift', 'Hinge drift', .1, 0, 1, .01),
            P('ribbon', 'Edge ribbon', .45, 0, 1, .01, 'A narrow secondary color plane travels beside the main fold.'),
            P('palette', 'Palette', 0, 0, 2, 1, choices=('Optical green / violet', 'Warm film / rose', 'Silver / ink')),
            P('color_phase', 'Color phase', 0., 0, 1, .01),
            P('color_speed', 'Color drift', .16, 0, 1, .01, 'Palette cycles per second, independent of the fold motion.'),
            P('wash', 'Color clouds', .75, 0, 1, .01, 'Broad moving patches within the color planes.'),
            P('shading', 'Fold shading', .6, 0, 1, .01),
            P('saturation', 'Color saturation', 1., 0, 1.5, .01),
            P('light', 'Exposure', 1., 0, 2, .01),
        )),
        Module('film_emulsion', 'Color emulsion',
               'Soft optical edges, color registration and fresh film-like grain. Works on every image source.', (
            P('softness', 'Optical softness', 2.2, 0, 8, .1, 'Pixels at a 720-pixel reference edge.'),
            P('bleed', 'Color bleed', 3., 0, 14, .1, 'Spread color locally while retaining the image structure.'),
            P('registration', 'Color registration', 2.5, 0, 12, .1, 'Small channel offsets create colored fringes along edges.'),
            P('edge_ink', 'Dark edge', .4, 0, 1, .01, 'Dark optical seams around strong image transitions.'),
            P('grain', 'Grain amount', .075, 0, .3, .005),
            P('grain_size', 'Grain size', 1.2, .5, 4, .1, 'Pixels at a 720-pixel reference edge. Fine grain stays visible in lower resolution previews.'),
            P('chroma', 'Grain color', .35, 0, 1, .01),
            P('flicker', 'Exposure flutter', .025, 0, .2, .005),
            P('cadence', 'Grain cadence', 25., 1, 60, 1),
            P('mix', 'Mix', 1., 0, 1, .01),
        )),
    )


PALETTES = (
    ((.28,.65,.33),(.57,.74,.39),(.74,.67,.32),(.74,.18,.30),
     (.58,.025,.48),(.23,.13,.45),(.16,.48,.48),(.33,.64,.39)),
    ((.75,.52,.29),(.73,.36,.35),(.65,.17,.41),(.34,.14,.42),
     (.27,.39,.40),(.48,.62,.42),(.71,.66,.38),(.75,.56,.40)),
    ((.16,.18,.2),(.28,.3,.31),(.46,.47,.45),(.69,.68,.61),
     (.76,.75,.68),(.55,.57,.56),(.32,.35,.36),(.18,.20,.23)),
)


def _colors(coordinate, palette):
    colors = np.asarray(PALETTES[int(palette)], np.float32)
    phase = coordinate * len(colors)
    index = np.floor(phase).astype(np.int32)
    blend = (phase-index)[...,None]
    blend = blend*blend*(3-2*blend)
    return colors[index%len(colors)]*(1-blend)+colors[(index+1)%len(colors)]*blend


def transition_progress(progress, eased, params, *, rotation=False):
    """Endpoint-flat acceleration with an optional, restrained follow-through.

    The unmodified curve is returned exactly for older documents. Color and
    texture never use this curve, and no history is needed when scrubbing.
    """
    strength = params.get('transition_ease', 0.)
    settle = params.get('turn_settle', 0.) if rotation else 0.
    if not strength and not settle:
        return eased
    t = max(0., min(1., progress))
    # Finish the main gesture early; give its arrival time to breathe.
    u = min(1., t / .72)
    driven = u*u*u*(u*(u*6-15)+10)
    result = eased + strength*(driven-eased)
    if settle and 0.35 < t < 1.:
        tail = (t-.35)/.65
        result += settle*.075*math.sin(math.pi*tail)**2
    return result


def _shape_spec(p):
    shape = p.get('shape', 0)
    if shape == 0: return int(p['sides']), 0.
    return ((3, 0.), (4, math.pi/4), (4, 0.), (5, 0.), (6, 0.), (0, 0.))[shape-1]


def _shape_bounds_center(p, angle):
    sides, offset = _shape_spec(p)
    if not sides: return 0., 0.
    angles = np.arange(sides)*math.tau/sides + math.pi/2 + offset + math.radians(angle)
    vertices = np.stack((np.cos(angles), np.sin(angles)), axis=-1)*.4
    return (vertices.min(axis=0)+vertices.max(axis=0))*.5


def prismatic_frame(p, size, seconds, preset):
    w,h = size
    cw,ch = content_size(preset,size)
    unit = min(cw,ch)
    dx,dy = object_offset(preset,size)
    t = seconds*preset.get('speed',1.)
    # Integrated speed, with positive derivative for either rotation direction.
    turn = p['rotation_speed']*(t+p['turn_variation']*math.sin(t*.85)/.85)
    angle = p['rotation']+turn
    cx = w*.5+dx+unit*p['drift']*.5*math.sin(t*.53)
    cy = h*.5-.06*ch+dy+unit*p['drift']*.65*math.sin(t*.41+.3)
    if p.get('center_shape', 0):
        # Center the visible bounds, including the triangle's uneven extents.
        bx, by = _shape_bounds_center(p, angle)
        centered_x = w*.5+dx-bx*unit*p['size']
        centered_y = h*.5+dy-by*unit*p['size']
        gather = p['gather']
        cx += (centered_x-cx)*gather
        cy += (centered_y-cy)*gather
    return (cx,cy),unit,angle


def _polygon_field(x,y,sides,radius):
    # Inward distance to the nearest side of a regular convex polygon.
    result = np.full_like(x,100.)
    apothem = radius*math.cos(math.pi/sides)
    for i in range(sides):
        angle = math.pi/2+math.pi/sides+i*math.tau/sides
        result = np.minimum(result,apothem-x*math.cos(angle)-y*math.sin(angle))
    return result


def closed_shape_field(u, v, p):
    sides, angle = _shape_spec(p)
    if not sides: return .4-np.hypot(u,v)
    if angle:
        u, v = u*math.cos(angle)+v*math.sin(angle), -u*math.sin(angle)+v*math.cos(angle)
    return _polygon_field(u,v,sides,.4)


def _cloud(x,y,time,seed):
    """Smooth, evolving lattice noise, anchored in object coordinates."""
    ix=np.floor(x).astype(np.int64); iy=np.floor(y).astype(np.int64)
    fx=x-ix; fy=y-iy; ft=time-math.floor(time)
    fx=fx*fx*(3-2*fx); fy=fy*fy*(3-2*fy); ft=ft*ft*(3-2*ft)
    def plane(tick):
        def lattice(dx,dy):
            n=((ix+dx)*73856093 ^ (iy+dy)*19349663 ^ tick*83492791 ^ seed) & 0xffffffff
            n=((n ^ (n >> 13))*1274126177) & 0xffffffff
            return ((n ^ (n >> 16)) & 0xffffff)/float(0xffffff)*2-1
        return ((1-fx)*lattice(0,0)+fx*lattice(1,0))*(1-fy)+((1-fx)*lattice(0,1)+fx*lattice(1,1))*fy
    tick=math.floor(time)
    return plane(tick)*(1-ft)+plane(tick+1)*ft


def render_prismatic_field(arr,p,seconds,preset):
    h,w = arr.shape[:2]
    (cx,cy),unit,angle = prismatic_frame(p,(w,h),seconds,preset)
    t = seconds*preset.get('speed',1.)
    yy,xx = np.mgrid[:h,:w].astype(np.float32)
    x=(xx-cx)/unit; y=(yy-cy)/unit
    a=math.radians(angle)
    u=(x*math.cos(a)+y*math.sin(a))/p['size']
    v=(-x*math.sin(a)+y*math.cos(a))/p['size']
    phase=math.tau*(t/p['fold_period']+p['fold_phase'])
    aperture=p['opening']*(1-p['fold_depth']*(.5-.5*math.cos(phase)))
    wedge=(aperture*np.abs(v)-np.abs(u))/math.sqrt(1+aperture**2)
    polygon=closed_shape_field(u,v,p)
    field=wedge*(1-p['gather'])+polygon*p['gather']
    coverage=np.clip(field*unit*p['size']+.5,0,1)[...,None]
    cloud=(.19*_cloud(x*2.1,y*2.1,t*.43,int(preset['seed']))+
           .075*_cloud(x*4.7,y*4.7,t*.31,int(preset['seed'])+917))*p['wash']
    color=p['color_phase']+t*p['color_speed']
    background=_colors(color+x*.045+y*.07+cloud,p['palette'])
    front=_colors(color+.46+u*.05+v*.035+cloud*.45,p['palette'])
    # The hinge shadow belongs to the open planes. Let it recede as they
    # gather, with a flat landing at the closed shape, instead of leaving a
    # permanent dark crease through the polygon. Keep the outer seam below.
    hinge_shading=p['shading']*(1-p['gather'])**3
    shade=1-hinge_shading*.42*np.exp(-np.abs(u)/(np.abs(v)*.3+.03))
    result=background*(1-coverage)+front*coverage*shade[...,None]
    # A narrow opposed blade is part of the geometry, not a full-screen stripe.
    ribbon_field=(aperture*.075*np.abs(v)-np.abs(u-v*aperture*.78))
    ribbon=np.clip(ribbon_field*unit*p['size']+.5,0,1)*(1-p['gather'])*p['ribbon']
    if p['gather'] > 0:
        # The secondary plane must close with the primary fold. Fading its
        # opacity alone leaves an infinite diagonal through the background,
        # especially when the final shape is small. Reuse the evolving mask
        # so every size/shape follows the same antialiased silhouette.
        ribbon *= coverage[...,0]
    result=result*(1-ribbon[...,None])+_colors(color+.16+cloud,p['palette'])*ribbon[...,None]
    seam=np.exp(-np.abs(field)*unit*p['size']/2.)*p['shading']*.32
    result*=1-seam[...,None]
    luma=result.mean(axis=2,keepdims=True)
    return np.asarray((luma+(result-luma)*p['saturation'])*p['light'],np.float32)


def _blur(arr,radius):
    image=Image.fromarray(np.uint8(np.clip(arr,0,1)*255))
    return np.asarray(image.filter(ImageFilter.GaussianBlur(radius)),np.float32)/255.


def render_film_emulsion(arr,p,seconds,speed,seed,reference):
    if not p['mix']: return arr
    h,w=arr.shape[:2]; scale=min(reference)/720.
    image=_blur(arr,p['softness']*scale) if p['softness'] else arr.copy()
    if p['bleed']:
        soft=_blur(image,p['bleed']*scale)
        # Chroma diffusion; do not turn the entire picture into a soft cloud.
        luma=image.mean(axis=2,keepdims=True)
        image=luma+soft-soft.mean(axis=2,keepdims=True)
    if p['registration']:
        offsets=p['registration']*scale*np.array((1.,-.2,-.8))
        x=np.arange(w,dtype=np.float32)
        for c,offset in enumerate(offsets):
            coord=np.clip(x+offset,0,w-1); left=coord.astype(int); right=np.minimum(left+1,w-1)
            image[...,c]=image[:,left,c]*(1-(coord-left))+image[:,right,c]*(coord-left)
    if p['edge_ink']:
        soft=_blur(arr,max(.5,4*scale))
        edge=np.abs(arr-soft).mean(axis=2)
        image*=1-np.clip(edge*p['edge_ink']*2,0,.6)[...,None]
    t=seconds*speed; tick=max(0,math.floor(t*p['cadence']+1e-8))
    rng=np.random.default_rng((seed+tick*7919)%(2**32))
    if p['grain']:
        grain_scale=max(1.,p['grain_size']*scale)
        gw,gh=max(2,round(w/grain_scale)),max(2,round(h/grain_scale))
        noise=rng.normal(0,1,(gh,gw,3)).astype(np.float32)
        if (gw,gh)!=(w,h):
            noise=np.stack([np.asarray(Image.fromarray(noise[...,c]).resize((w,h),Image.Resampling.BILINEAR)) for c in range(3)],axis=-1)
        mono=noise[...,:1]
        noise=mono*(1-p['chroma'])+noise*p['chroma']
        image+=noise*p['grain']*(.55+.45*np.sqrt(np.clip(image,0,1)))
    image*=1+p['flicker']*(.55*math.sin(t*17.3)+.3*math.sin(t*31.7)+.15*math.sin(t*7.1))
    return np.asarray(arr*(1-p['mix'])+image*p['mix'],np.float32)
