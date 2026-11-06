"""Close a single Pleated study as editable camera samples, not baked pixels."""
import copy
import math

from synth import MODULE_BY_ID
from synth_composition import normalize_composition
from synth_performance import source_time


def close_pleated_study(project, closing_seconds=2.):
    result=normalize_composition(project)
    source=result['source'];duration=source['duration'];fps=result['fps']
    if len(result['sections'])!=1 or result['sections'][0]['duration']!=duration or result['sections'][0]['loops']!=1:
        raise ValueError('Close a single full-length Pleated study')
    performance=result.get('visual_performance',{})
    if performance.get('tracks'):
        raise ValueError('Finish recorded performance movements before closing this camera study')
    specs=MODULE_BY_ID['pleated_field'].params
    keys={p.key:p for p in specs}
    prefix='pleated_field.'
    original=copy.deepcopy(source)
    def state_at(seconds):
        cue=next(c for c in reversed(original['cues']) if c['time']<=seconds+1e-9)
        return copy.deepcopy(original['states'][cue['state']])
    first=state_at(0)
    final=state_at(duration-1/fps)
    if 'pleated_field' not in first.get('enabled',[]):
        raise ValueError('This camera closer needs a Pleated field source')
    if final['overrides'].get(prefix+'symmetry',0)!=first['overrides'].get(prefix+'symmetry',0):
        raise ValueError('The closing camera shot must use the opening mirror mode')
    states={};cues=[];start=duration-closing_seconds
    if not 1/fps<closing_seconds<duration:raise ValueError('Choose a closing move shorter than the study')
    for frame in range(round(duration*fps)):
        t=frame/fps
        if t<start:
            sample=source_time(performance,t,duration,fps)
            state=state_at(sample)
        else:
            state=copy.deepcopy(final)
            u=(t-start)/closing_seconds
            weight=u*u*u*(10+u*(-15+6*u))
            for key,spec in keys.items():
                path=prefix+key
                a=final['overrides'].get(path,spec.default)
                b=first['overrides'].get(path,spec.default)
                if spec.choices:value=b
                elif key=='size':value=math.exp(math.log(a)*(1-weight)+math.log(b)*weight)
                else:value=a*(1-weight)+b*weight
                state['overrides'][path]=round(value) if spec.kind=='int' else max(spec.minimum,min(spec.maximum,value))
        state['overrides'][prefix+'loop_seconds']=duration
        name=f'loop-camera-{frame:03}'
        states[name]=state;cues.append(dict(time=t,state=name,transition='cut',duration=0.))
    source.update(states=states,cues=cues)
    source.pop('time_map',None)
    if performance:
        # Preserve the user's slower camera through the new source samples;
        # do not apply the same speed a second time after composing the loop.
        result['visual_performance']['values'].update(pace=100.,fluidity=0.)
    result['generated_sound']['seamless_loop']=True
    result['name']='Pleated signal / acid loop'
    return normalize_composition(result)
