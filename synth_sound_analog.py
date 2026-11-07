"""Band-limited oscillator ensembles and a streaming stereo ambience bus.

Shared building blocks, independent of visual source or note scheduling. This
is a virtual-analog sound design, not a circuit emulation of a named synth.
"""
import math
from functools import lru_cache
import numpy as np

RATE = 48000
TABLE_SIZE=2048
FILTER_STEPS=64


@lru_cache(maxsize=64)
def filtered_saw(harmonics,resonance):
    """Four-pole spectral tables: smooth pitch and cutoff interpolation at run time."""
    h=np.arange(1,harmonics+1)[None,:]
    cutoff=2**np.linspace(-3,8,FILTER_STEPS)[:,None]
    ratio=h/cutoff
    response=(1+resonance*3*np.exp(-(np.log2(ratio)/.48)**2))/(1+ratio*ratio)**2
    spectrum=np.zeros((FILTER_STEPS,TABLE_SIZE//2+1),complex)
    spectrum[:,1:harmonics+1]=response/h*np.exp(-4j*np.arctan(ratio))/(2j)
    table=np.fft.irfft(spectrum,n=TABLE_SIZE,axis=1)*TABLE_SIZE
    return np.concatenate((table,table[:,:1]),axis=1)


def lookup(table,phase,cutoff_ratio):
    x=np.mod(phase,1)*TABLE_SIZE;ix=x.astype(int);fx=x-ix
    y=np.clip((np.log2(np.maximum(cutoff_ratio,.125))+3)*(FILTER_STEPS-1)/11,0,FILTER_STEPS-1)
    iy=np.floor(y).astype(int);fy=y-iy;jy=np.minimum(iy+1,FILTER_STEPS-1)
    a=table[iy,ix]*(1-fx)+table[iy,ix+1]*fx
    b=table[jy,ix]*(1-fx)+table[jy,ix+1]*fx
    return a+(b-a)*fy


def analog_defaults():
    return dict(wave=.3, unison=3, detune=6., sub=.22, cutoff=1400.,
                resonance=.25, sweep=1.5, attack=.012, drive=.22)


def pad_defaults():
    return dict(enabled=False, follow_root=True, pitch=82.4069, pitch_mode='note',
                octave=1,cutoff=780., detune=7., motion=.35, reverb=.7)


def space_defaults():
    return dict(chorus=0., decay=3.2, damping=.65)


def ensemble(t, hz, settings, *, period=None):
    """Saw/pulse bank with a moving four-pole spectral lowpass and sub.

    Harmonics are removed above Nyquist before synthesis. A spectral filter
    envelope avoids per-sample Python recursion, keeping live edits inexpensive.
    Sustained voices use whole cycles when looping, including their slow drift.
    """
    n=len(t);out=np.zeros((n,2));count=int(settings['unison'])
    detunes=np.linspace(-1,1,count) if count>1 else np.array([0.])
    cutoff=np.asarray(settings['cutoff'])
    for i, spread in enumerate(detunes):
        f=hz*2**(spread*settings['detune']/1200)
        if period:f=round(f*period)/period
        harmonics=min(64,int(RATE*.42/f))
        if not harmonics:continue
        # Modulation stays below a cent; the root and scale remain audible.
        rate=(max(1,round(.23*period))/period) if period else .23
        drift=.018*np.sin(math.tau*rate*t+i*1.71)*settings['detune']/10
        phase=f*t+(drift+i*.71)/math.tau
        pwm=.48+.055*np.sin(math.tau*rate*t+i*.9)
        table=filtered_saw(harmonics,settings['resonance']);ratio=cutoff/f
        saw=lookup(table,phase,ratio)
        pulse=saw-lookup(table,phase+pwm,ratio)
        wave=(1-settings['wave'])*saw+settings['wave']*pulse*.7
        pan=spread*.65
        out[:,0]+=wave*math.sqrt((1-pan)*.5)/count
        out[:,1]+=wave*math.sqrt((1+pan)*.5)/count
    subhz=hz*.5
    if period:subhz=round(subhz*period)/period
    out+=settings['sub']*.7*np.sin(math.tau*subhz*t)[:,None]
    drive=1+settings['drive']*2
    return np.tanh(out*drive)/math.sqrt(drive)


def analog_note(age,hz,voice):
    settings=dict(voice['analog']);t=np.maximum(age,0.)
    settings['cutoff']=settings['cutoff']*2**(settings['sweep']*np.exp(-t/(voice['decay']*.7)))
    tone=ensemble(t,hz,settings)
    a=np.clip(t/settings['attack'],0,1);a=a*a*(3-2*a)
    tail=np.clip((6*voice['decay']-t)/.04,0,1);tail=tail*tail*(3-2*tail)
    envelope=a*np.exp(-t*.8/voice['decay'])*tail*(age>=0)
    return tone*envelope[:,None]


def root_pad(t,hz,settings,period=None):
    cycle=period or 20.
    movement=settings['motion']
    cutoff=settings['cutoff']*2**(movement*.45*np.sin(math.tau*t/cycle))
    p=dict(analog_defaults(),wave=.58,unison=3,detune=settings['detune'],
           sub=.08,cutoff=cutoff,resonance=.12,drive=.12)
    # Root and octave only; no chord tones that could change the chosen scale.
    hz*=2**settings['octave']
    tone=ensemble(t,hz,p,period=period)
    tone+=.22*ensemble(t,hz*2,p,period=period)
    return tone*(.88+.12*np.cos(math.tau*t/cycle))[:,None]


class Delay:
    def __init__(self,length):
        self.buffer=np.zeros((length,2));self.position=0

    def read(self,n):
        index=(self.position+np.arange(n))%len(self.buffer)
        return self.buffer[index].copy()

    def write(self,values):
        index=(self.position+np.arange(len(values)))%len(self.buffer)
        self.buffer[index]=values;self.position=(self.position+len(values))%len(self.buffer)

    def inherit(self,old):
        self.buffer=old.buffer.copy();self.position=old.position


class StereoSpace:
    """Modulated chorus plus damped parallel combs and allpass diffusion.

    Fixed small internal packets make the delay network independent of the
    host's block size. State transfers across live knob edits without clearing
    the room. All delays are fixed; decay/damping change feedback, not memory.
    """
    def __init__(self,settings,period=None):
        self.settings=settings;self.period=period
        self.chorus=Delay(2048)
        self.combs=[Delay(n) for n in (1559,1747,1999,2137,2357,2647,2903,3251)]
        self.diffusers=[Delay(n) for n in (241,557,383,809)]
        self.last=[np.zeros(2) for _ in self.combs]

    def inherit(self,old):
        self.chorus.inherit(old.chorus)
        for a,b in zip(self.combs,old.combs):a.inherit(b)
        for a,b in zip(self.diffusers,old.diffusers):a.inherit(b)
        self.last=[x.copy() for x in old.last]

    def process(self,dry,send,start):
        out=np.empty_like(dry);s=self.settings
        for offset in range(0,len(dry),128):
            x=dry[offset:offset+128];excite=send[offset:offset+128];n=len(x)
            t=(start+offset+np.arange(n))/RATE
            rate=round(.4*self.period)/self.period if self.period else .4
            lag=RATE*(.018+.003*np.sin(math.tau*rate*t[:,None]+np.array([0.,math.pi/2])))
            at=(self.chorus.position+np.arange(n)[:,None]-lag)%len(self.chorus.buffer)
            lo=np.floor(at).astype(int);frac=at-lo
            delayed=self.chorus.buffer[lo,np.arange(2)]*(1-frac)+self.chorus.buffer[(lo+1)%len(self.chorus.buffer),np.arange(2)]*frac
            self.chorus.write(x)
            mixed=x*(1-.3*s['chorus'])+delayed*.6*s['chorus']
            wet=np.zeros_like(x)
            for i,line in enumerate(self.combs):
                tail=line.read(n)
                previous=np.vstack((self.last[i],tail[:-1]));self.last[i]=tail[-1].copy()
                damp=tail*(1-.48*s['damping'])+previous*(.48*s['damping'])
                feedback=10**(-3*len(line.buffer)/(RATE*s['decay']))
                # Alternating crossfeed spreads even a centered root in stereo.
                feed=excite if i%2==0 else excite[:,::-1]
                line.write(feed*.22+damp*feedback)
                wet+=tail[:,::-1] if i%3==0 else tail
            wet*=.25
            for line in self.diffusers:
                delayed=line.read(n);value=wet+delayed*.55
                line.write(value);wet=delayed-value*.55
            out[offset:offset+n]=mixed+wet
        return out
