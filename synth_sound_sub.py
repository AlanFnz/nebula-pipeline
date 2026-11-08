"""Dry mono bass anchored to the root of the pad, with no chord or detune."""
import math
import numpy as np
from synth_sound_analog import RATE


def sub_defaults():
    return dict(enabled=False, octaves_below=2, body=.12, cutoff=120.)


def normalize_sub(raw,number):
    out=sub_defaults()
    if not isinstance(raw,dict):raise ValueError('Invalid sub bass settings')
    out['enabled']=raw.get('enabled',False)
    if type(out['enabled']) is not bool:raise ValueError('Sub bass enabled must be a checkbox')
    for key,lo,hi in (('octaves_below',1,4),('body',0,1),('cutoff',40,800)):
        out[key]=number(raw.get(key,out[key]),'Sub bass '+key,lo,hi)
    if out['octaves_below']!=int(out['octaves_below']):raise ValueError('Sub bass octaves must be a whole number')
    out['octaves_below']=int(out['octaves_below'])
    return out


def sub_frequency(root,pad_octave,settings):
    return root*2**(pad_octave-settings['octaves_below'])


class SubVoice:
    def __init__(self,root,pad_octave,settings,period=None):
        hz=sub_frequency(root,pad_octave,settings)
        if period:hz=max(1,round(hz*period))/period
        self.hz=hz;self.partials=[]
        for harmonic,weight in ((1,1.),(2,.18*settings['body']),(3,.08*settings['body']),
                                (4,.025*settings['body'])):
            frequency=hz*harmonic
            if frequency>=RATE*.4 or weight==0:continue
            # A two-pole spectral low-pass shapes only this layer. It leaves no
            # recursive filter state to interrupt when the knob moves live.
            weight/=math.sqrt(1+(frequency/settings['cutoff'])**4)
            self.partials.append((frequency,weight))

    def render(self,t):
        mono=np.zeros(len(t))
        for frequency,weight in self.partials:mono+=weight*np.sin(math.tau*frequency*t)
        return np.repeat(mono[:,None],2,axis=1)
