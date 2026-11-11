"""Stable identities and neutral controls for the optical relic's seven parts."""
import math

PARTS = (
    ('base', 'Pedestal', False),
    ('upper', 'Upper hoop', True),
    ('lower', 'Lower hoop', True),
    ('spindle', 'Spindle & central body', True),
    ('crown', 'Crown', True),
    ('left', 'Left pin', True),
    ('right', 'Right pin', True),
)


RELIC_PARTS = PARTS
ORBITAL_PARTS = (PARTS[0],
    *((f'ring{i}',f'Ring {i}'+(' / outer' if i==1 else ' / inner' if i==5 else ''),True) for i in range(1,6)),
    ('core','Center sphere',True), ('finial','Top finial',False))
PARTS = RELIC_PARTS + ORBITAL_PARTS[1:]


def parts_for(scene=0):
    return ORBITAL_PARTS if scene == 1 else RELIC_PARTS


def parameters(P):
    result = []
    for part, label, follows in PARTS:
        prefix = 'part_' + part + '_'
        def add(key, name, default, lo=0, hi=1, step=.01, hint='', choices=()):
            result.append(P(prefix+key, label+' · '+name, default, lo, hi, step, hint, choices=choices))
        add('visible', 'Visible', 1, step=1, choices=('Hidden','Visible'))
        add('follow', 'Follow assembly', int(follows), step=1,
            hint='Follow the shared assembly turn. Off keeps this part in place while its own motion remains active.',
            choices=('Independent','Follow assembly'))
        for axis, direction in (('x','right'), ('y','back'), ('z','up')):
            add('position_'+axis, 'Position '+axis.upper(), 0., -4., 4., .01,
                'Offset in 3D scene units before the assembly turn. Positive moves '+direction+'.')
            add('rotation_'+axis, 'Rotation '+axis.upper(), 0., -360., 360., 1.,
                'Rotate around this part’s own pivot; its original placement is preserved at zero.')
            add('scale_'+axis, 'Scale '+axis.upper(), 1., .1, 3., .01,
                'Scale around this part’s own pivot. 1 keeps the original shape.')
        add('period', 'Rotation period', 8.75, .25, 60., .05,
            'Seconds per independent motion cycle at global speed 1. Whole turns close at the end of this cycle.')
        for axis in 'xyz':
            add('turns_'+axis, 'Turns '+axis.upper(), 0, -8, 8, 1,
                'Whole turns per cycle. Negative reverses direction; 0 leaves this axis still.')
        add('phase', 'Starting phase', 0., hint='Starting position within the independent rotation cycle.')
        add('ease', 'Turn easing', 0., 0., .95, .01,
            'Smoothly vary the speed without stopping or reversing.')
        add('inherit', 'Use assembly material', 1, step=1,
            hint='Use the shared material. Turn off to use this part’s color, metallic amount and roughness.',
            choices=('Own material','Use assembly material'))
        add('hue', 'Material hue', .15)
        add('saturation', 'Material saturation', .15)
        add('metallic', 'Metallic', 1.)
        add('roughness', 'Roughness', .24, .05, .9)
    return tuple(result)


def part_controls(key):
    """Return stable part ID and field, or None for an assembly control."""
    if not key.startswith('part_'): return None
    for part, _, _ in PARTS:
        prefix = 'part_'+part+'_'
        if key.startswith(prefix): return part, key[len(prefix):]
    return None


def part_poses(p, seconds, speed=1.):
    """Only authored nonneutral pieces enter the cache/protocol.

    Motion is resolved at timeline time, so seeking, repeats and export agree.
    Disabled custom materials and idle motion do not invalidate cached renders.
    """
    result = {}
    for part, _, follows in parts_for(p.get('scene',0)):
        prefix = 'part_'+part+'_'
        def value(key, default): return p.get(prefix+key, default)
        position = [value('position_'+a, 0.) for a in 'xyz']
        rotation = [value('rotation_'+a, 0.) for a in 'xyz']
        scale = [value('scale_'+a, 1.) for a in 'xyz']
        turns = [value('turns_'+a, 0) for a in 'xyz']
        visible = bool(value('visible', 1)); follow = bool(value('follow', int(follows)))
        material = None if value('inherit', 1) else {
            key:value(key, default) for key,default in
            (('hue',.15),('saturation',.15),('metallic',1.),('roughness',.24))}
        active = (not visible or follow != follows or any(position) or any(rotation)
                  or scale != [1.,1.,1.] or any(turns) or material is not None)
        if not active: continue
        phase = round((seconds*speed/value('period',8.75)+value('phase',0.)) % 1., 10) % 1.
        cycle = phase-value('ease',0.)*math.sin(math.tau*phase)/math.tau
        rotation = [round((r+360*t*cycle) % 360., 8) % 360. for r,t in zip(rotation,turns)]
        result[part] = dict(position=position, rotation=rotation, scale=scale,
                            visible=visible, follow=follow, material=material)
    return result


def groups():
    result = []
    for page, (part, label, _) in enumerate(PARTS, 1):
        prefix = 'blender_scene.part_'+part+'_'
        transform = ['visible','follow'] + [kind+'_'+axis for kind in ('position','rotation','scale') for axis in 'xyz']
        for title, opened, fields in (
            ('Transform', True, transform),
            ('Independent motion', False, ['period','turns_x','turns_y','turns_z','phase','ease']),
            ('Material', False, ['inherit','hue','saturation','metallic','roughness'])):
            result.append((page, label+' / '+title, opened, tuple(prefix+f for f in fields)))
    return tuple(result)


AUTOMATION_FIELDS = frozenset(kind+'_'+axis for kind in ('position','rotation','scale') for axis in 'xyz')
AUTOMATION_TARGETS = frozenset('blender_scene.part_'+part+'_'+key
                              for part,_,_ in PARTS for key in AUTOMATION_FIELDS)
