"""A sustained, pitched vowel ensemble, independent of note/visual scheduling.

Harmonic glottal tables supply the vowels; no samples or external voices are
needed. Tables and slow modulation wrap with the project for seamless loops.
"""
import math
from functools import lru_cache
import numpy as np
from synth_sound_analog import RATE, TABLE_SIZE, PAD_HARMONIES


def choir_defaults():
    return dict(enabled=False, octave=0, vowel=.6, detune=5., motion=.35,
                cutoff=4200., air=.12, width=.85, reverb=.9)


def normalize_choir(raw, number):
    out=choir_defaults()
    if not isinstance(raw,dict):raise ValueError('Invalid choir settings')
    enabled=raw.get('enabled',False)
    if type(enabled) is not bool:raise ValueError('Choir enabled must be a checkbox')
    out['enabled']=enabled
    for key,lo,hi in (('octave',-1,1),('vowel',0,1),('detune',0,12),('motion',0,1),
                      ('cutoff',500,9000),('air',0,1),('width',0,1),('reverb',0,1)):
        out[key]=number(raw.get(key,out[key]),'Choir '+key,lo,hi)
    if out['octave']!=int(out['octave']):raise ValueError('Choir octave must be a whole number')
    out['octave']=int(out['octave'])
    return out


@lru_cache(maxsize=128)
def vowel_tables(hz, cutoff):
    # Two broad vowel resonances, with a softer high formant. The fundamental
    # stays present so changing the vowel never changes the chord's tuning.
    harmonics=np.arange(1,min(96,int(RATE*.4/hz))+1)
    frequencies=harmonics*hz
    tables=[]
    for centers,widths in (((350,900,2400),(130,210,400)),((780,1150,2800),(210,270,470))):
        response=np.full(len(harmonics),.1)
        for center,width,gain in zip(centers,widths,(1.,.85,.3)):
            response+=gain*np.exp(-.5*((frequencies-center)/width)**2)
        response/=harmonics**1.15*(1+(frequencies/cutoff)**4)
        if len(response):response[0]+=.25
        response/=max(.001,np.linalg.norm(response))
        spectrum=np.zeros(TABLE_SIZE//2+1,complex)
        spectrum[1:len(harmonics)+1]=response*np.exp(-.15j*harmonics)/(2j)
        wave=np.fft.irfft(spectrum,n=TABLE_SIZE)*TABLE_SIZE
        tables.append(np.append(wave,wave[0]))
    return tables


@lru_cache(maxsize=1)
def breath_table():
    size=RATE*2
    rng=np.random.default_rng(8147)
    spectrum=np.fft.rfft(rng.normal(size=(2,size)),axis=1)
    f=np.fft.rfftfreq(size,1/RATE)
    spectrum*=np.exp(-.5*((f-3300)/1500)**2)*(1-np.exp(-(f/1100)**4))
    wave=np.fft.irfft(spectrum,n=size,axis=1)
    wave/=np.sqrt(np.mean(wave**2,axis=1))[:,None]
    return np.concatenate((wave,wave[:,:1]),axis=1)


def sample_table(table, phase):
    size=len(table)-1;x=np.mod(phase,1)*size
    index=np.floor(x).astype(int);fraction=x-index
    return table[index]*(1-fraction)+table[index+1]*fraction


class ChoirVoice:
    def __init__(self,hz,pad,settings,period=None):
        self.settings=settings;self.period=period
        self.cycle=period or 20.
        self.parts=[]
        root=hz*2**(pad['octave']+settings['octave'])
        intervals=next(notes for key,_,notes in PAD_HARMONIES if key==pad['harmony'])
        weights=(1.,.68,.62,.48,.38)[:len(intervals)]
        norm=math.sqrt(sum(w*w for w in weights))*math.sqrt(3)
        for note,(interval,weight) in enumerate(zip(intervals,weights)):
            for singer in range(3):
                spread=singer-1
                f=root*2**(interval/12+spread*settings['detune']/1200)
                if period:f=max(1,round(f*period))/period
                if f>=RATE*.4:continue
                oo,ah=vowel_tables(f,settings['cutoff'])
                pan=np.clip(spread*.5+(-1 if note%2 else 1)*.25,-1,1)*settings['width']
                self.parts.append((f,oo,ah,weight/norm,np.sqrt([(1-pan)*.5,(1+pan)*.5]),note*1.37+singer*2.11))
        self.breath=breath_table() if settings['air'] else None

    def render(self,t):
        out=np.zeros((len(t),2));s=self.settings
        slow=math.tau*t/self.cycle
        for f,oo,ah,weight,pan,offset in self.parts:
            # Small periodic breath/vibrato keeps each singer moving separately.
            phase=f*t+offset/math.tau+s['motion']*.018*np.sin(slow*3+offset)
            vowel=np.clip(s['vowel']+s['motion']*.12*np.sin(slow+offset),0,1)
            a=sample_table(oo,phase);b=sample_table(ah,phase)
            tone=(a+(b-a)*vowel)*weight*(.9+.1*np.cos(slow+offset))
            out+=tone[:,None]*pan
        if self.breath is not None:
            rate=max(1,round(self.cycle/2))/self.cycle if self.period else .5
            air=np.column_stack([sample_table(table,t*rate) for table in self.breath])
            out+=air*(.035*s['air']*(.85+.15*np.cos(slow)))[:,None]
        return out
