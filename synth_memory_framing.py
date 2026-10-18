"""Authoring-only bounds of the Memory object's path on the export frame grid.

No renderer, recipe or source clock is changed by measuring a path. Results are
cached by geometry/timing, so tweaking color or tape damage does not resample it.
"""
import copy
import json
import math
from bisect import bisect_right
from functools import lru_cache

import numpy as np

from synth_canvas import content_size
from synth_composition import compile_composition, section_placements
from synth_memory import memory_frame, memory_pose
from synth_retime import mapped_time
from synth_sequence import _state_preset, resolve_sequence_frame

AMPLITUDES = ('image_memory.amplitude_x', 'image_memory.amplitude_y')
PATH_KEYS = ('path', 'travel', 'amplitude_x', 'amplitude_y', 'period', 'variation',
             'phase', 'size', 'shape', 'sides', 'rotation', 'spin', 'mix')
MAX_AMPLITUDE = 10000.


class MotionBounds:
    def __init__(self, centers, origins, slopes, extents, size):
        self.centers, self.origins, self.slopes = centers, origins, slopes
        self.extents, self.size = extents, size

    def bounds(self, axis, value=None):
        positions = self.centers[:, axis] if value is None else self.origins[:, axis]+self.slopes[:, axis]*value
        return (float(np.min(positions+self.extents[:, axis*2])),
                float(np.max(positions+self.extents[:, axis*2+1])))

    def midpoint(self, axis, value=None):
        low, high = self.bounds(axis, value)
        return (low+high)*.5

    def maximum(self, axis):
        """Largest amplitude fitting around the current path's bounding center."""
        center = self.midpoint(axis)
        available = 2*max(0., min(center, self.size[axis]-center))
        def fits(value):
            low, high = self.bounds(axis, value)
            return high-low <= available
        # Several inherited clip offsets can already exceed the canvas even
        # with no travel. Do not pretend an amplitude limit can fix that layout.
        if not fits(0.): return None
        if not np.any(self.slopes[:, axis]): return None
        low, high = 0., MAX_AMPLITUDE
        if fits(high): return high
        for _ in range(40):
            mid = (low+high)*.5
            if fits(mid): low=mid
            else: high=mid
        return math.floor(low*100)/100


def motion_bounds(project, index=None, sequence=None):
    seq = sequence if sequence is not None else compile_composition(project)
    paths = {'image_memory.'+key for key in PATH_KEYS} | {'speed', 'object_x', 'object_y'}
    # Keep source presets so omitted parameters retain their authored defaults.
    reduced = {key: seq[key] for key in ('duration', 'fps', 'canvas', 'seed', 'render_version', 'cues')}
    if 'time_map' in seq: reduced['time_map'] = seq['time_map']
    reduced['states'] = {name: dict(preset=state['preset'],
        enabled=['image_memory'] if 'image_memory' in state.get('enabled', ()) else [],
        overrides={key:value for key,value in state.get('overrides', {}).items() if key in paths})
        for name,state in seq['states'].items()}
    spans=[]
    for owner,start,end,_ in section_placements(project):
        if index is not None and owner != index: continue
        local = project['sections'][owner]['effects'].get('image_memory', {}).get('params', {})
        blocked = [index is None and path in local for path in AMPLITUDES]
        spans.append((round(start*seq['fps']), round(end*seq['fps']), blocked))
    return _measure(json.dumps((reduced,spans), sort_keys=True))


@lru_cache(maxsize=8)
def _measure(key):
    seq,spans = json.loads(key)
    width,height = size = (seq['canvas']['width'],seq['canvas']['height'])
    cue_times = [cue['time'] for cue in seq['cues']]
    presets = {name:_state_preset(seq,name) for name in seq['states']}
    # At most the application's one-hour / 120 fps timeline. No image buffers.
    data = np.empty((sum(end-start for start,end,_ in spans),10),np.float64)
    count=0
    for start,end,blocked in spans:
        for frame in range(start,end):
            t=frame/seq['fps']; cue=seq['cues'][max(0,bisect_right(cue_times,t)-1)]
            preset=presets[cue['state']]
            effect_time=mapped_time(seq.get('time_map'),t,'effects')
            if cue.get('transition') not in (None,'cut','sweep','flash') and t < cue['time']+cue.get('duration',0):
                _,_,effect_time,_,_,_,_,preset=resolve_sequence_frame(seq,t,normalized=True)
            source=next((m for m in preset['modules'] if m['id']=='image_memory' and m['enabled']),None)
            if source is None or source['params']['mix']<=0: continue
            p=source['params']; center,radius,angle=memory_frame(p,size,effect_time,preset)
            cw,ch=content_size(preset,size)
            x,y,_=memory_pose(dict(p,amplitude_x=100.,amplitude_y=100.),effect_time*preset['speed'])
            slopes=(0. if blocked[0] else x*cw/100., 0. if blocked[1] else y*ch/100.)
            origins=tuple(center[a]-slopes[a]*p.get('amplitude_'+axis,100.) for a,axis in enumerate(('x','y')))
            # Current silhouette only: glow, drifting memories and later VHS
            # distortions are intentionally free to extend beyond this envelope.
            edge=max(.65,min(cw,ch)/720.*.7)
            extent=(-radius-edge,radius+edge,-radius-edge,radius+edge)
            if p['shape']==2:
                angles=np.arange(p['sides'])*math.tau/p['sides']+math.pi/p['sides']-math.pi*.5+math.radians(angle)
                xx,yy=np.cos(angles)*radius,np.sin(angles)*radius
                edge/=math.cos(math.pi/p['sides'])
                extent=(xx.min()-edge,xx.max()+edge,yy.min()-edge,yy.max()+edge)
            data[count]=(*center,*origins,*slopes,*extent);count+=1
    if not count: return None
    data=data[:count].copy();data.setflags(write=False)
    return MotionBounds(data[:,:2],data[:,2:4],data[:,4:6],data[:,6:],size)


def center_path(project, index=None, sequence=None):
    bounds=motion_bounds(project,index,sequence)
    if bounds is None: return copy.deepcopy(project)
    result=copy.deepcopy(project);target=result if index is None else result['sections'][index]
    for axis,name in enumerate(('x','y')):
        value=target['geometry']['position_'+name]+bounds.size[axis]*.5-bounds.midpoint(axis)
        if not -4096<=value<=4096: raise ValueError('This path needs a position beyond the canvas placement range.')
        target['geometry']['position_'+name]=round(value,6)
    return result


def edit_amplitude(project, path, value, index=None, sequence=None):
    bounds=motion_bounds(project,index,sequence)
    result=copy.deepcopy(project);target=result if index is None else result['sections'][index]
    axis=AMPLITUDES.index(path)
    if bounds is not None:
        maximum=bounds.maximum(axis)
        if maximum is not None: value=min(value,maximum)
        shift=bounds.midpoint(axis)-bounds.midpoint(axis,value)
        key='position_'+('x','y')[axis]
        position=target['geometry'][key]+shift
        if not -4096<=position<=4096: raise ValueError('Center the path before extending its amplitude further.')
        target['geometry'][key]=round(position,6)
    target['effects'].setdefault('image_memory',{'mode':'recipe','params':{}})['params'][path]=value
    return result
