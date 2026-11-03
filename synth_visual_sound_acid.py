"""A pitched triangle, moving resonant filter, and gesture-triggered melodies.

No noise bed or continuous pitch/velocity link. The visual gesture chooses when
a short phrase begins; note envelopes continue on the independent audio clock.
"""
import math

import numpy as np

from synth_visual_sound import RATE, CONTROL_RATE, _smooth

SCALES = {'pentatonic': (0,3,5,7,10), 'minor': (0,2,3,5,7,8,10),
          'dorian': (0,2,3,5,7,9,10)}


def phrase_pattern(config, phrase):
    """Scale-degree palette and step count, independent of the visual onset."""
    original=(0,2,1,3) if phrase%2==0 else (2,0,1)
    if config['version']!=3: return original
    count=config.get('arp_notes',4)
    steps=config.get('arp_steps',0) or len(original)
    direction=config.get('arp_pattern','visual')
    if direction=='visual':
        return tuple((original[j%len(original)]+(j//len(original))*len(original))%count for j in range(steps))
    if direction=='down': cycle=tuple(range(count-1,-1,-1))
    elif direction=='up_down': cycle=tuple(range(count))+tuple(range(count-2,0,-1))
    else: cycle=tuple(range(count))
    return tuple(cycle[j%len(cycle)] for j in range(steps))


def gesture_notes(signals, config, *, include_rests=False):
    """Causal hysteresis: motion surges/expansion turns, with space to breathe.

    No timeline-specific cue table or random clock. A held or uniformly moving
    image does not produce a repeated arpeggiator. Automatic length keeps the
    original 3–4 notes. Fixed lengths finish before another phrase starts.
    """
    from synth_sound_sequence import step_seconds, sequence_phrase
    custom = config.get('arp_mode') == 'sequence' and config['version'] == 3
    if custom and config['sequence_trigger'] == 'loop':
        length = step_seconds(config) * config['sequence_length']
        return [note for phrase, start in enumerate(np.arange(0., signals['time'][-1], length))
                for note in sequence_phrase(config, start, float(np.interp(start, signals['time'], signals['motion'])), phrase, signals['time'][-1], include_rests)
                if np.interp(note['time'], signals['time'], signals['presence']) > .12]
    times=signals['time'];initial=signals['expansion'][0]
    e=_smooth(signals['expansion']-initial,.10)+initial
    m=_smooth(signals['motion'],.10)
    slope=_smooth(np.diff(e,prepend=e[0])*CONTROL_RATE,.10)
    notes=[];last=-10.;phrase_end=-10.;armed=True;previous_slope=0.;previous_motion=0.;phrase=0
    scale=SCALES[config['scale']]
    for i,t in enumerate(times):
        if slope[i]<-.08 or m[i]<.4: armed=True
        onset=armed and ((slope[i]>.16 and previous_slope<=.16) or (m[i]>.72 and previous_motion<=.72))
        reopening=signals['opening'][i]>.5
        if signals['presence'][i]>.12 and (onset or reopening) and t-last>1.25 and t>=phrase_end and t<times[-1]-.45:
            last=float(t);armed=False
            if custom:
                step = step_seconds(config)
                start = math.ceil((float(t) - 1e-9) / step) * step
                notes.extend(sequence_phrase(config, start, m[i], phrase, times[-1], include_rests))
                phrase_end = start + config['sequence_length'] * step
                phrase += 1
                previous_slope=slope[i];previous_motion=m[i]
                continue
            # A coherent motif, varied by the current geometry, not random notes.
            degree=min(len(scale)-1,int(e[i]*len(scale)))
            pattern=phrase_pattern(config,phrase)
            step=(.19-.055*min(1.,m[i]))/config['arp_rate']
            if config['version']==3 and config.get('arp_steps',0): phrase_end=float(t+len(pattern)*step)
            for j,offset in enumerate(pattern):
                index=degree+offset
                semitones=12+scale[index%len(scale)]+12*(index//len(scale))
                notes.append(dict(time=float(t+j*step),semitones=semitones,
                                  duration=step*1.85,velocity=(.85 if j==0 else .64)+.12*m[i],
                                  pan=(-.22 if (j+phrase)%2==0 else .22)))
            phrase+=1
        previous_slope=slope[i];previous_motion=m[i]
    return notes


def arpeggio_activity(signals,config):
    activity=np.zeros_like(signals['time'])
    if not config['enabled'] or not config['connections']['arpeggio']['enabled']: return activity
    for note in gesture_notes(signals,config):
        age=signals['time']-note['time']
        activity=np.maximum(activity,np.exp(-np.maximum(age,0)/.095)*(age>=0)*(age<note['duration']))
    return activity


def triangle(phase, frequency):
    """Additive triangle; omit partials above the audible Nyquist margin."""
    out=np.zeros_like(phase)
    for n in range(1,32,2):
        if n*frequency >= RATE*.45: break
        out += (-1 if (n-1)//2%2 else 1)*np.sin(n*phase)/(n*n)
    return out*(8/math.pi**2)


def resonant_lowpass(samples, cutoff, resonance, state):
    """Trapezoidal SVF (Andrew Simper, Cytomic), with smooth per-sample cutoff.

    https://www.cytomic.com/files/dsp/SvfLinearTrapOptimised2.pdf
    The damping range stays strictly positive, including at maximum resonance.
    """
    g=np.tan(np.pi*cutoff/RATE);k=1/(.7+resonance*6.8)
    a1=1/(1+g*(g+k));a2=g*a1;a3=g*a2
    s1,s2=state;out=np.empty_like(samples)
    for i,(x,c1,c2,c3) in enumerate(zip(samples.tolist(),a1.tolist(),a2.tolist(),a3.tolist())):
        v3=x-s2;v1=c1*s1+c2*v3;v2=s2+c2*s1+c3*v3
        s1=2*v1-s1;s2=2*v2-s2
        out[i]=v2
    return out,(s1,s2)


def acid_blocks(sequence,config,signals,cancel):
    total=round(sequence['duration']*RATE)
    amount={key:c['amount'] if config['enabled'] and c['enabled'] else 0.
            for key,c in config['connections'].items()}
    gate=_smooth(signals['presence'],.025)
    expansion=_smooth(signals['expansion'],config['smoothing'])
    motion=_smooth(signals['motion'],config['smoothing'])
    notes=gesture_notes(signals,config) if amount['arpeggio'] else []
    states=[(0.,0.),(0.,0.)]
    for start in range(0,total,RATE):
        cancel.check();length=min(RATE,total-start);t=(start+np.arange(length))/RATE
        g,e,m=[np.interp(t,signals['time'],v) for v in (gate,expansion,motion)]
        # Stable musical root: expression comes from spectrum and articulation.
        body=triangle(math.tau*config['pitch']*t,config['pitch'])*(.16+.08*e)*amount['body']
        melody=np.zeros((length,2));pluck=np.zeros(length)
        for note in notes:
            if note['time']>=t[-1]+1/RATE or note['time']+note['duration']<=t[0]: continue
            age=t-note['time'];u=np.maximum(age,0)
            env=(1-np.exp(-u/.006))*np.exp(-u/.095)*np.clip((note['duration']-u)/.06,0,1)
            env*=age>=0
            hz=config['pitch']*2**(note['semitones']/12)
            tone=triangle(math.tau*hz*u,hz)*env*note['velocity']*.42*amount['arpeggio']
            melody[:,0]+=tone*(1-note['pan']);melody[:,1]+=tone*(1+note['pan'])
            pluck=np.maximum(pluck,env)
        opening=np.clip((.06+.46*e+.52*m)*amount['filter']+.22*pluck*amount['filter'],0,1)
        cutoff=config['cutoff']*(config['sweep']/config['cutoff'])**opening
        channels=[]
        fade=np.minimum(np.clip(t/.045,0,1),np.clip((total/RATE-t)/.045,0,1))
        for channel in range(2):
            # Mild pre-filter drive exposes the triangle's odd harmonics.
            source=np.tanh((body+melody[:,channel])*2.6)
            filtered,states[channel]=resonant_lowpass(source,cutoff,config['resonance'],states[channel])
            channels.append(np.tanh(filtered*.85)*.72*config['gain']*g*fade)
        yield np.stack(channels,axis=1).astype(np.float32)
