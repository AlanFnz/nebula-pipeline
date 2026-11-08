"""Struck metallic resonators for a rising, overlapping chime cascade."""
import math

import numpy as np


def chime_defaults():
    return dict(shimmer=.35, strike=.006, tuning='metallic')


def normalize_chime_resonance(raw,number):
    out=chime_defaults()
    if not isinstance(raw,dict):raise ValueError('Invalid chime resonance')
    for field,lo,hi in (('shimmer',0,1),('strike',.002,.04)):
        out[field]=number(raw.get(field,out[field]),'Chimes '+field,lo,hi)
    out['tuning']=raw.get('tuning','metallic')
    if out['tuning'] not in ('metallic','harmonic'):raise ValueError('Choose a supported chime resonance tuning')
    return out


def chime_layer_defaults():
    """Opt-in overlay; old documents keep both original color-wave voices."""
    return dict(enabled=False, engine='chimes', pitch=329.6275569128699,
                pitch_mode='note', scale='minor', span=24., decay=.9,
                brightness=.66, trigger=.5, polyphony=0,
                chimes=chime_defaults(), reverb=.42, delay=.06)


def normalize_chime_layer(raw, number):
    from synth_sound_sequence import snapped_frequency
    from synth_lattice_sound import SCALES
    out=chime_layer_defaults()
    if not isinstance(raw,dict):raise ValueError('Invalid chimes layer')
    out['enabled']=raw.get('enabled',False)
    if type(out['enabled']) is not bool:raise ValueError('Chimes enabled must be a checkbox')
    for field,lo,hi in (('pitch',40,1760),('span',12,48),('decay',.15,3.),
                        ('brightness',0,1),('trigger',.05,.95),('reverb',0,1),('delay',0,1),('polyphony',0,8)):
        out[field]=number(raw.get(field,out[field]),'Chimes '+field,lo,hi)
    if out['polyphony']!=int(out['polyphony']):raise ValueError('Chimes sustain voices must be a whole number')
    out['polyphony']=int(out['polyphony'])
    for field,choices in (('pitch_mode',('hz','note')),('scale',SCALES)):
        out[field]=raw.get(field,out[field])
        if out[field] not in choices:raise ValueError('Choose a supported chimes '+field)
    if out['pitch_mode']=='note':out['pitch']=snapped_frequency(out['pitch'],40,1760)
    out['chimes']=normalize_chime_resonance(raw.get('chimes',out['chimes']),number)
    return out


def chime_note(age, hz, settings, rate=48000):
    """Evaluate a note by age so seeks and live/export packets share its phase.

    Inharmonic upper modes give the metal its character; the strongest mode
    retains the selected scale note. Small paired-mode offsets shimmer without
    moving note attacks or introducing random noise.
    """
    t=np.maximum(age,0.);decay=settings['decay'];brightness=settings['brightness']
    chime=settings['chimes']
    ratios=np.array([1.,2.76,5.40,8.93,13.35,18.65])
    tuned=chime.get('tuning','metallic')=='harmonic'
    if tuned:ratios=np.array([1.,3.,5.,9.,13.,19.])
    frequencies=hz*ratios
    offsets=2**(chime['shimmer']*np.array([1.2,2.8,3.6,4.8,5.5,6.3])/1200.)
    # Keep the tuned fundamental exact; shimmer lives only in upper modes.
    if tuned:offsets[0]=1.
    keep=frequencies*offsets<rate*.44
    frequencies=frequencies[keep];ratios=ratios[keep];offsets=offsets[keep]
    amplitudes=np.array([1.,.42,.25,.14,.08,.045])[keep]
    amplitudes*=np.exp(-ratios*(1-brightness)*.24)
    damping=(.75+.35*np.sqrt(ratios))/decay
    phase=math.tau*frequencies[:,None]*t
    modes=.67*np.sin(phase)+.33*np.sin(phase*offsets[:,None])
    tone=np.sum(amplitudes[:,None]*np.exp(-damping[:,None]*t)*modes,axis=0)
    attack=np.clip(t/chime['strike'],0,1);attack=attack*attack*(3-2*attack)
    tail=np.clip((6*decay-t)/.06,0,1);tail=tail*tail*(3-2*tail)
    return tone*attack*tail*(age>=0)
