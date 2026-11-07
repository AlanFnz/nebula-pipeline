"""A phase-continuous sine following the radial center of the visible pulse."""
import hashlib
import math
import numpy as np

from synth_visual_sound import CONTROL_RATE, _smooth
from synth_sound_loop import smooth_cycle


def wave_defaults():
    return dict(enabled=False, low_pitch=82.4069, high_pitch=164.8138,
                low_pitch_mode='note', high_pitch_mode='note', glide=.08, reverb=.15)


def normalize_wave(raw, number):
    from synth_sound_sequence import snapped_frequency
    out=wave_defaults()
    if not isinstance(raw,dict):raise ValueError('Invalid wave sine settings')
    out['enabled']=raw.get('enabled',False)
    if type(out['enabled']) is not bool:raise ValueError('Wave sine enabled must be a checkbox')
    for key in ('low_pitch','high_pitch'):
        out[key]=number(raw.get(key,out[key]),'Wave sine '+key,40,1760)
        mode=raw.get(key+'_mode','note')
        if mode not in ('hz','note'):raise ValueError('Choose wave sine tuning')
        out[key+'_mode']=mode
        if mode=='note':out[key]=snapped_frequency(out[key],40,1760)
    if out['low_pitch']>out['high_pitch']:raise ValueError('Wave sine high pitch must be above its low pitch')
    for key,lo,hi in (('glide',.01,.5),('reverb',0,1)):
        out[key]=number(raw.get(key,out[key]),'Wave sine '+key,lo,hi)
    return out


def wave_position(p,seconds,preset):
    from synth_lattice import lattice_frame,wave_distance,pulse_size
    w,h=preset['width'],preset['height']
    (cx,cy),spacing,_=lattice_frame(p,(w,h),preset)
    # Stable cell membership avoids jumps when a border cell shrinks offscreen.
    x,y=np.meshgrid(np.arange(math.ceil(-cx/spacing),math.floor((w-cx)/spacing)+1),
                    np.arange(math.ceil(-cy/spacing-.5),math.floor((h-cy)/spacing-.5)+1)+.5)
    if not x.size:return .5
    distance=np.abs(wave_distance(x,y,p))
    radii=pulse_size(distance,seconds*preset.get('speed',1.),p)
    baseline=1-p['pulse']+p['pulse']*p['minimum']
    weights=np.maximum(radii*radii-baseline*baseline,0.)
    if weights.sum()<1e-12:return .5
    return float(np.sum(distance/max(float(distance.max()),1e-9)*weights)/weights.sum())


class WaveSine:
    def __init__(self,signals,settings,duration,looping):
        self.duration=duration
        count=max(1,math.ceil(duration*CONTROL_RATE))
        self.times=np.linspace(0,duration,count+1)
        source=signals['time']
        radius=np.interp(self.times,source,signals.get('lattice_radius',np.full_like(source,.5)))
        present=np.interp(self.times,source,signals['presence'])>.002
        visible=radius[present]
        lo,hi=(float(visible.min()),float(visible.max())) if visible.size else (.5,.5)
        # Small/static gestures stay subtle rather than amplifying numerical noise.
        position=np.clip(.5+(radius-(lo+hi)*.5)/max(.15,hi-lo),0,1)
        smoother=smooth_cycle if looping else _smooth
        position=smoother(position,settings['glide'])
        self.amplitude=smoother(present.astype(float),.06)
        self.frequency=settings['low_pitch']*(settings['high_pitch']/settings['low_pitch'])**position
        if looping:
            self.frequency[-1]=self.frequency[0]
        increments=(self.frequency[:-1]+self.frequency[1:])*.5*np.diff(self.times)
        if looping:
            # Close oscillator phase with a sub-cent tuning adjustment, not a fade.
            correction=round(float(increments.sum()))/float(increments.sum())
            self.frequency*=correction;increments*=correction
        self.phase=np.r_[0.,np.cumsum(increments)]
        self.slope=np.diff(self.frequency)/np.diff(self.times)
        self.cache_key=hashlib.sha256(self.frequency.tobytes()+self.amplitude.tobytes()).hexdigest()

    def render(self,times):
        indices=np.clip(np.searchsorted(self.times,times,side='right')-1,0,len(self.slope)-1)
        dt=times-self.times[indices]
        phase=self.phase[indices]+self.frequency[indices]*dt+.5*self.slope[indices]*dt*dt
        level=np.interp(times,self.times,self.amplitude)
        mono=np.sin(math.tau*phase)*level*.2
        return np.repeat(mono[:,None],2,axis=1)
