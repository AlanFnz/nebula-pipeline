"""Portable visual instruments: relative controls, recorded gestures and adapters.

The fast stage operates on the finished frame and can reuse prepared pixels.
Surface adapters alter resolved object parameters and therefore need a render.
Both paths are shared by preview and export. Neutral settings are exact bypass.
"""
from dataclasses import dataclass
import copy
import math
import numpy as np
from PIL import Image


@dataclass(frozen=True)
class Control:
    key: str
    title: str
    low: float
    high: float
    default: float
    group: str
    suffix: str = ' %'
    hint: str = ''


COMMON = (
    Control('scale','Scale',25,250,100,'Frame'),
    Control('x','Horizontal',-100,100,0,'Frame'),
    Control('y','Vertical',-100,100,0,'Frame'),
    Control('rotation','Rotation',-180,180,0,'Frame','°'),
    Control('pace','Pace',25,200,100,'Motion',hint='Speed of the visual sequence. The timeline and soundtrack keep their duration.'),
    Control('fluidity','Fluidity',-100,100,0,'Motion',hint='Shape acceleration inside each second of visual motion. Positive values ease into and out of movement.'),
    Control('twist','Torsion',-100,100,0,'Motion',hint='Twist the image around its center.'),
    Control('irregularity','Irregularity',0,100,0,'Motion',hint='Organic displacement with a repeatable, evolving rhythm.'),
    Control('texture','Texture',0,100,0,'Finish',hint='Add fine, moving grain to the original texture.'),
    Control('color','Color rotation',-180,180,0,'Finish','°'),
)

# Adapters describe relative mappings; nothing branches on a study name.
SURFACES = {
    'pleated_field': (
        (Control('opening','Opening',-100,100,0,'Surface',hint='Expand or contract the original optical opening.'),
         (('aperture','add',2.5),)),
        (Control('relief','Relief',25,200,100,'Surface',hint='Coordinate fold depth and shadow strength.'),
         (('depth','multiply',1.),('seams','multiply',.6))),
        (Control('density','Fold density',25,200,100,'Surface'),
         (('density','multiply',1.),)),
    ),
}
SURFACE_CONTROLS = {c.key:c for adapter in SURFACES.values() for c,_ in adapter}
CONTROLS = {c.key:c for c in COMMON} | SURFACE_CONTROLS
FAST = frozenset(c.key for c in COMMON)
MAX_POINTS = 20000


def defaults():
    return dict(version=1,enabled=True,values={k:c.default for k,c in CONTROLS.items()},tracks={})


def _number(value,low,high,label):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not low<=value<=high:
        raise ValueError(f'{label} must be between {low:g} and {high:g}')
    return float(value)


def normalize_performance(raw=None):
    if raw is None:return defaults()
    if not isinstance(raw,dict) or raw.get('version')!=1 or type(raw.get('version')) is not int:
        raise ValueError('Unsupported visual performance version')
    if set(raw)-{'version','enabled','values','tracks'}:raise ValueError('Unknown visual performance field')
    out=defaults();out['enabled']=raw.get('enabled',True)
    if type(out['enabled']) is not bool:raise ValueError('Visual performance enabled must be a checkbox')
    values=raw.get('values',{});tracks=raw.get('tracks',{})
    if not isinstance(values,dict) or set(values)-CONTROLS.keys():raise ValueError('Unknown visual control')
    if not isinstance(tracks,dict) or set(tracks)-CONTROLS.keys():raise ValueError('Unknown recorded visual control')
    for k,v in values.items():
        c=CONTROLS[k];out['values'][k]=_number(v,c.low,c.high,c.title)
    count=0
    for k,points in tracks.items():
        if not isinstance(points,list):raise ValueError('Recorded controls need keyframes')
        count+=len(points)
        if count>MAX_POINTS:raise ValueError('Visual recording has too many keyframes')
        c=CONTROLS[k];previous=-1;clean=[]
        for point in points:
            if not isinstance(point,(tuple,list)) or len(point)!=2:raise ValueError('Invalid visual keyframe')
            at=_number(point[0],0,1,'Keyframe position');v=_number(point[1],c.low,c.high,c.title)
            if at<=previous:raise ValueError('Visual keyframes must be ordered without duplicates')
            clean.append([at,v]);previous=at
        if clean:out['tracks'][k]=clean
    return out


def values_at(config,seconds,duration):
    if not config or not config.get('enabled',True):return defaults()['values']
    result=defaults()['values'];result.update(config.get('values',{}))
    fraction=max(0.,min(1.,seconds/max(duration,1e-9)))
    for k,points in config.get('tracks',{}).items():
        if points:result[k]=float(np.interp(fraction,[p[0] for p in points],[p[1] for p in points]))
    return result


def _series(config, key, fractions):
    points = config.get('tracks', {}).get(key)
    if points:
        return np.interp(fractions, [p[0] for p in points], [p[1] for p in points])
    return np.full_like(fractions, config.get('values', {}).get(key, CONTROLS[key].default), dtype=float)


def source_times(config, times, duration, fps):
    """One visual clock for cached playback, export, and sound analysis."""
    times = np.asarray(times, dtype=float)
    if not config or not config.get('enabled', True):
        return times
    tracks = config.get('tracks', {})
    rate = config.get('values', {}).get('pace', 100) / 100
    fluidity = config.get('values', {}).get('fluidity', 0)
    if not tracks.get('pace') and not tracks.get('fluidity') and rate == 1 and fluidity == 0:
        return times
    duration = max(duration, 1e-9)
    fractions = np.clip(times / duration, 0, 1)
    points = tracks.get('pace')
    if points:
        # Integrate each linear interval exactly, without scanning all recorded
        # points for every audio sample. This also avoids phase jumps in a take.
        xs = np.array([0., *[p[0] for p in points if 0 < p[0] < 1], 1.])
        ys = np.interp(xs, [p[0] for p in points], [p[1] / 100 for p in points])
        lengths = np.diff(xs)
        slopes = np.diff(ys) / lengths
        areas = np.r_[0., np.cumsum(lengths * (ys[:-1] + ys[1:]) * .5)]
        indices = np.clip(np.searchsorted(xs, fractions, side='right') - 1, 0, len(xs) - 2)
        dx = fractions - xs[indices]
        clock = (areas[indices] + dx * ys[indices] + .5 * slopes[indices] * dx * dx) * duration
    else:
        clock = times * rate
    fluid = _series(config, 'fluidity', fractions) / 100
    whole = np.floor(clock)
    u = clock - whole
    clock = whole + u + fluid * .9 * (u * u * (3 - 2 * u) - u)
    return np.clip(np.floor((clock % duration) * fps + 1e-8) / fps, 0, max(0, duration - 1 / fps))


def source_time(config, seconds, duration, fps):
    return float(source_times(config, [seconds], duration, fps)[0])


def base_document(document):
    """Immutable shallow view of pixels that can be prepared once and reused."""
    if not document:return document
    out=document
    if 'visual_performance' in document:
        out=dict(document);config=document['visual_performance'];surface=defaults()
        surface['enabled']=config.get('enabled',True)
        for k in SURFACE_CONTROLS:
            surface['values'][k]=config.get('values',{}).get(k,CONTROLS[k].default)
            if k in config.get('tracks',{}):surface['tracks'][k]=config['tracks'][k]
        if surface['enabled'] and (surface['tracks'] or any(surface['values'][k]!=CONTROLS[k].default for k in SURFACE_CONTROLS)):
            out['visual_performance']=surface
        else:out.pop('visual_performance',None)
    if document.get('schema_version')==7:
        if out is document:out=dict(out)
        out['schema_version']=6 if 'generated_sound' in out else 5 if 'audio_reactivity' in out else 4 if 'soundtrack' in out else 3 if 'video_segments' in out else 2 if 'footage' in out else 1
    if 'source' in document:
        source=base_document(document['source'])
        if source is not document['source']:
            if out is document:out=dict(out)
            out['source']=source
    return out


def available_controls(sequence):
    from synth_sequence import _state_preset
    from synth_instances import base_id
    ids=set()
    for name,state in sequence.get('states',{}).items():
        if 'enabled' in state:
            ids.update(base_id(key) for key in state['enabled'])
        else:
            ids.update(base_id(m['id']) for m in _state_preset(sequence,name)['modules'] if m['enabled'])
    return (*COMMON,*(c for key,adapter in SURFACES.items() if key in ids for c,_ in adapter))


def apply_surface(preset,config,seconds,duration):
    values=values_at(config,seconds,duration)
    if all(values[k]==c.default for k,c in SURFACE_CONTROLS.items()):return preset
    from synth import MODULE_BY_ID
    from synth_instances import base_id
    out=copy.deepcopy(preset)
    for entry in out['modules']:
        module=base_id(entry['id'])
        if not entry['enabled'] or module not in SURFACES:continue
        specs={p.key:p for p in MODULE_BY_ID[module].params}
        for control,mappings in SURFACES[module]:
            delta=(values[control.key]-control.default)/100
            for key,mode,strength in mappings:
                old=entry['params'][key];v=old+delta*strength if mode=='add' else old*max(.05,1+delta*strength)
                entry['params'][key]=max(specs[key].minimum,min(specs[key].maximum,v))
    return out


def apply_frame(image,config,seconds,duration,seed=0):
    v=values_at(config,seconds,duration)
    if all(v[k]==CONTROLS[k].default for k in FAST-{'pace','fluidity'}):return image
    w,h=image.size;scale=v['scale']/100;angle=math.radians(v['rotation']);twist=v['twist']/100
    irregular=v['irregularity']/100
    def point(x,y):
        unit=min(w,h)
        xx=(x-w*(.5+v['x']/100))/(scale*unit);yy=(y-h*(.5+v['y']/100))/(scale*unit)
        radius=xx*xx+yy*yy;a=-angle+twist*radius*3
        c,s=math.cos(a),math.sin(a);u=xx*c-yy*s;vv=xx*s+yy*c
        u+=irregular*.022*math.sin(yy*13+seconds*3.1)+irregular*.008*math.sin(yy*29-seconds*1.7)
        vv+=irregular*.016*math.sin(xx*11-seconds*2.3)
        return (u*unit+w*.5,vv*unit+h*.5)
    if any(v[k]!=CONTROLS[k].default for k in ('scale','x','y','rotation','twist','irregularity')):
        mesh=[];grid=16
        for j in range(grid):
            for i in range(grid):
                x0,x1=round(i*w/grid),round((i+1)*w/grid);y0,y1=round(j*h/grid),round((j+1)*h/grid)
                if x1>x0 and y1>y0:mesh.append(((x0,y0,x1,y1),(*point(x0,y0),*point(x0,y1),*point(x1,y1),*point(x1,y0))))
        # Use the average frame color in the newly exposed canvas.
        fill=image.resize((1,1)).getpixel((0,0))
        image=image.transform((w,h),Image.Transform.MESH,mesh,Image.Resampling.BICUBIC,fillcolor=fill)
    if v['color']:
        hsv=np.array(image.convert('HSV'));hsv[:,:,0]=((hsv[:,:,0].astype(np.int16)+round(v['color']*255/360))%256).astype(np.uint8)
        image=Image.fromarray(hsv,'HSV').convert('RGB')
    if v['texture']:
        rng=np.random.default_rng((int(seed)+round(seconds*120)*104729)&0xffffffff)
        rgb=np.asarray(image,dtype=np.float32);noise=rng.normal(0,v['texture']*.10,(h,w,1)).astype(np.float32)
        image=Image.fromarray(np.rint(np.clip(rgb+noise,0,255)).astype(np.uint8),'RGB')
    return image


def apply_signals(signals, config, duration, fps):
    """Retimed source analysis plus an approximate framing/motion contribution.

    These are internal control signals, not analysis of the finished RGB image.
    Color and grain do not affect the existing motion-driven instrument.
    """
    keys = FAST - {'texture', 'color'}
    if not config or not config.get('enabled', True):
        return signals
    if not any(k in keys for k in config.get('tracks', {})) and all(
        config.get('values', {}).get(k, CONTROLS[k].default) == CONTROLS[k].default for k in keys
    ):
        return signals
    times = signals['time']
    clocks = source_times(config, times, duration, fps)
    out = {k: (times if k == 'time' else np.interp(clocks, times, v)) for k, v in signals.items()}
    fractions = np.clip(times / max(duration, 1e-9), 0, 1)
    values = {k: _series(config, k, fractions) for k in keys}
    scales = values['scale'] / 100
    xs, ys = values['x'] / 100, values['y'] / 100
    def coverage(offset):
        return np.clip(np.minimum(1., .5 + offset + scales * .5) - np.maximum(0., .5 + offset - scales * .5), 0, 1)
    area = coverage(xs) * coverage(ys)
    out['presence'] = out['presence'] * area
    out['expansion'] = np.clip(out['expansion'] + np.log2(scales) / 4, 0, 1)
    pose = np.stack([np.log2(scales), xs, ys, values['rotation'] / 180, values['twist'] / 100], axis=1)
    change = np.linalg.norm(np.diff(pose, axis=0, prepend=pose[:1]), axis=1) * 120
    from synth_visual_sound import _smooth
    # Pace affects the amount of motion as well as its location in time.
    rate = values['pace'] / 100
    out['motion'] = np.clip(out['motion'] * rate + _smooth(np.tanh(change) * .5, .06) + values['irregularity'] * .0015, 0, 1)
    return out
