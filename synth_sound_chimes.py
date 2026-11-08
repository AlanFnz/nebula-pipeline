"""Struck metallic resonators for a rising, overlapping chime cascade."""
import math

import numpy as np


def chime_defaults():
    return dict(shimmer=.35, strike=.006)


def chime_note(age, hz, settings, rate=48000):
    """Evaluate a note by age so seeks and live/export packets share its phase.

    Inharmonic upper modes give the metal its character; the strongest mode
    retains the selected scale note. Small paired-mode offsets shimmer without
    moving note attacks or introducing random noise.
    """
    t=np.maximum(age,0.);decay=settings['decay'];brightness=settings['brightness']
    chime=settings['chimes']
    ratios=np.array([1.,2.76,5.40,8.93,13.35,18.65])
    frequencies=hz*ratios
    offsets=2**(chime['shimmer']*np.array([1.2,2.8,3.6,4.8,5.5,6.3])/1200.)
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
