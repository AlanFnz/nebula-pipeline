"""Layered band-limited oscillators with click-softened notes and filter control."""
import math

import numpy as np

from synth_visual_sound import RATE, _smooth
from synth_visual_sound_acid import gesture_notes, resonant_lowpass
from synth_sound_mixer import make_mixer


def note_envelope(age,duration,attack,release):
    """Zero value and zero slope at both ends; a pluck without a hard edge."""
    u=np.maximum(age,0.)
    rise=np.sin(np.clip(u/attack,0.,1.)*np.pi/2)**2
    end=np.clip((duration-u)/min(release,duration*.6),0.,1.)
    fall=end*end*(3-2*end)
    return rise*np.exp(-u/release)*fall*(age>=0)


def instrument_note_duration(note,config):
    if config.get('arp_mode')=='sequence': return note['duration']+config['release']
    return max(note['duration'],config['attack']+config['release'])


def waveform(phase,hz,shape,density):
    fundamental=np.sin(phase)
    if shape=='sine': return fundamental
    out=fundamental.copy()
    limit=min(32,math.ceil(RATE*.42/hz))
    for n in range(2,limit):
        if shape=='triangle': weight=0. if n%2==0 else (-1 if (n-1)//2%2 else 1)/(n*n)
        elif shape=='square': weight=0. if n%2==0 else 1/n
        else: weight=(-1 if n%2==0 else 1)/n
        if not weight or not density: continue
        out+=density*weight*np.sin(n*phase)
    # Keep comparable fundamental level between shapes and density positions.
    return out*.8


def oscillator_bank(t,root,config,seed):
    """Absolute phase preserves continuity across blocks and deterministic seeks."""
    bank=np.zeros((len(t),2));weight=0.
    offsets=np.linspace(-1,1,config['unison']) if config['unison']>1 else np.array([0.])
    for index,osc in enumerate(config['oscillators']):
        if not osc['enabled'] or osc['level']==0: continue
        frequencies=[];phases=[]
        for voice,offset in enumerate(offsets):
            hz=root*2**((osc['transpose']+(osc['detune']+offset*config['detune'])/100)/12)
            # Keep the original phase arithmetic and accumulation order. Batch
            # unison waves with the same harmonic limit to reduce live DSP cost.
            phases.append(math.tau*(hz*t+((index*.173+voice*.137+(seed%997)*.00013)%1)))
            frequencies.append(hz)
        limits=[min(32,math.ceil(RATE*.42/hz)) for hz in frequencies]
        if len(set(limits))==1:
            signals=waveform(np.stack(phases),frequencies[0],osc['wave'],config['density'])
        else:
            signals=[waveform(p,hz,osc['wave'],config['density']) for p,hz in zip(phases,frequencies)]
        for signal,offset in zip(signals,offsets):
            pan=config['width']*(offset*.7+(index-1)*.22)
            bank[:,0]+=signal*math.sqrt(1-pan)*osc['level']/len(offsets)
            bank[:,1]+=signal*math.sqrt(1+pan)*osc['level']/len(offsets)
        weight+=osc['level']
    return bank/max(1.,weight)


def instrument_controls(signals,config):
    notes=gesture_notes(signals,config)
    pluck=np.zeros_like(signals['time'])
    link=config['connections']['arpeggio']
    if config['enabled'] and link['enabled'] and link['amount']>0:
        for note in notes:
            duration=instrument_note_duration(note,config)
            pluck=np.maximum(pluck,note_envelope(signals['time']-note['time'],duration,config['attack'],config['release']))
    # The note's filter accent has its own de-click smoothing; resonance cannot
    # amplify a sudden attack into a sharp transient. Evaluated before blocking.
    return notes,_smooth(pluck,.035)


class InstrumentVoice:
    """One stateful voice shared by offline export and the live monitor."""
    def __init__(self, sequence, config, signals):
        self.config=config;self.signals=signals
        total=round(sequence['duration']*RATE)
        amount={key:c['amount'] if config['enabled'] and c['enabled'] else 0.
                for key,c in config['connections'].items()}
        presence=signals['presence']
        continuity=config.get('continuity',0.)
        if continuity:
            # Visible area is not perceived loudness. Compress its dynamic range
            # before the existing de-click envelope, retaining exact zero for an
            # absent object. The default zero keeps earlier PCM sample-identical.
            presence=np.clip(presence,0.,1.)**(1-.9*continuity)
        gate=_smooth(presence,.035)
        expansion=_smooth(signals['expansion'],config['smoothing'])
        motion=_smooth(signals['motion'],config['smoothing'])
        notes,accent=instrument_controls(signals,config)
        if not amount['arpeggio']: notes=[]
        states=[(0.,0.),(0.,0.)]
        seed=int(sequence.get('seed',0))
        self.total=total
        self.amount=amount
        self.gate=gate
        self.expansion=expansion
        self.motion=motion
        self.notes=notes
        self.accent=accent
        self.states=states
        self.seed=seed
        self.mixer=make_mixer(config)

    def render(self, start, length):
        config=self.config
        signals=self.signals
        total=self.total
        amount=self.amount
        gate=self.gate
        expansion=self.expansion
        motion=self.motion
        notes=self.notes
        accent=self.accent
        states=self.states
        seed=self.seed
        t=(start+np.arange(length))/RATE
        g,e,m,a=[np.interp(t,signals['time'],v) for v in (gate,expansion,motion,accent)]
        body=oscillator_bank(t,config['pitch'],config,seed)*((.18+.08*e)*amount['body'])[:,None]
        melody=np.zeros((length,2))
        for n,note in enumerate(notes):
            duration=instrument_note_duration(note,config)
            if note['time']>=t[-1]+1/RATE or note['time']+duration<=t[0]: continue
            age=t-note['time'];u=np.maximum(age,0.)
            env=note_envelope(age,duration,config['attack'],config['release'])
            hz=config.get('arp_pitch',config['pitch'])*2**(note['semitones']/12)
            tone=oscillator_bank(u,hz,config,seed+n+1)*((env*note['velocity']*.40*amount['arpeggio'])[:,None])
            tone[:,0]*=1-note['pan']*.5;tone[:,1]*=1+note['pan']*.5
            melody+=tone
        body=self.mixer['body'].process(body)
        melody=self.mixer['arpeggio'].process(melody)
        # Opening is the manual bias; the motion link adds the live visual sweep.
        opening=np.clip(config['opening']+(.36*e+.42*m+.16*a)*amount['filter'],0,1)
        cutoff=config['cutoff']*(config['sweep']/config['cutoff'])**opening
        fade=np.minimum(np.clip(t/.06,0,1),np.clip((total/RATE-t)/.08,0,1))
        fade=fade*fade*(3-2*fade)
        channels=[]
        for channel in range(2):
            source=np.tanh((body[:,channel]+melody[:,channel])*(1.5+config['drive']*3))
            filtered,states[channel]=resonant_lowpass(source,cutoff,config['resonance'],states[channel])
            channels.append(np.tanh(filtered*.9)*.72*config['gain']*g*fade)
        return np.stack(channels,axis=1).astype(np.float32)


def instrument_blocks(sequence,config,signals,cancel,*,block_size=RATE):
    voice=InstrumentVoice(sequence,config,signals)
    for start in range(0,voice.total,block_size):
        cancel.check()
        yield voice.render(start,min(block_size,voice.total-start))
