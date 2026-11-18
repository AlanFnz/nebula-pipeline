"""Two instrument channels, before the existing shared drive and visual filter."""
import math

import numpy as np


CHANNELS = (('body', 'Drone'), ('arpeggio', 'Arpeggio'))
BANDS = (('low', 'Low', 120., 40., 600.),
         ('mid', 'Mid', 1000., 200., 6000.),
         ('high', 'High', 4000., 1000., 16000.))


def mixer_defaults(channels=CHANNELS):
    result={key: dict(level_db=0., mute=False, solo=False, eq_enabled=True,
                     **{field: value for band, _, hz, _, _ in BANDS
                        for field, value in ((band+'_db', 0.), (band+'_hz', hz))})
            for key, _ in channels}
    if 'chimes' in result:result['chimes'].update(highpass_enabled=False,highpass_hz=120.)
    return result


def normalize_mixer(raw, number, channels=CHANNELS):
    defaults = mixer_defaults(channels)
    if not isinstance(raw, dict) or set(raw) != set(defaults):
        raise ValueError('Mixer needs '+', '.join(title for _,title in channels)+' channels')
    for key, channel in defaults.items():
        entry = raw[key]
        if not isinstance(entry, dict): raise ValueError('Invalid mixer channel')
        for field in ('mute', 'solo', 'eq_enabled'):
            value = entry.get(field, channel[field])
            if type(value) is not bool: raise ValueError(f'Mixer {field} must be a checkbox')
            channel[field] = value
        ranges = [('level_db', -60., 6.)]
        for band, _, _, low, high in BANDS:
            ranges.extend(((band+'_db', -18., 18.), (band+'_hz', low, high)))
        for field, low, high in ranges:
            channel[field] = number(entry.get(field, channel[field]), f'mixer {key} {field}', low, high)
        if key=='chimes':
            enabled=entry.get('highpass_enabled',False)
            if type(enabled) is not bool:raise ValueError('Chimes high-pass must be a checkbox')
            channel['highpass_enabled']=enabled
            channel['highpass_hz']=number(entry.get('highpass_hz',120.),'Chimes high-pass frequency',20.,18000.)
    return defaults


def eq_coefficients(band, hz, gain, rate=48000):
    """RBJ/W3C Audio EQ Cookbook; shelf slope 1, broad bell Q = 0.8.

    https://www.w3.org/TR/audio-eq-cookbook/
    Return normalized b0,b1,b2,a1,a2; zero gain is an exact bypass.
    """
    if gain == 0: return None
    a = 10**(gain/40)
    w = math.tau*hz/rate; c = math.cos(w); s = math.sin(w)
    if band == 'mid':
        alpha = s/(2*.8)
        b = (1+alpha*a, -2*c, 1-alpha*a)
        den = (1+alpha/a, -2*c, 1-alpha/a)
    else:
        beta = math.sqrt(2*a)*s
        if band == 'low':
            b = (a*((a+1)-(a-1)*c+beta), 2*a*((a-1)-(a+1)*c), a*((a+1)-(a-1)*c-beta))
            den = ((a+1)+(a-1)*c+beta, -2*((a-1)+(a+1)*c), (a+1)+(a-1)*c-beta)
        else:
            b = (a*((a+1)+(a-1)*c+beta), -2*a*((a-1)+(a+1)*c), a*((a+1)+(a-1)*c-beta))
            den = ((a+1)-(a-1)*c+beta, 2*((a-1)-(a+1)*c), (a+1)-(a-1)*c-beta)
    return tuple(v/den[0] for v in (*b, *den[1:]))


def highpass_coefficients(hz,rate=48000):
    """Second-order Butterworth high-pass, 12 dB/octave."""
    w=math.tau*hz/rate;c=math.cos(w);alpha=math.sin(w)/math.sqrt(2)
    return tuple(v/(1+alpha) for v in ((1+c)/2,-(1+c),(1+c)/2,-2*c,1-alpha))


class MixerChannel:
    def __init__(self, config, solo_active=False):
        self.audible = not config['mute'] and (not solo_active or config['solo'])
        self.level = 10**(config['level_db']/20)
        self.coefficients = [eq_coefficients(band, config[band+'_hz'], config[band+'_db'])
                             if config['eq_enabled'] else None for band, *_ in BANDS]
        if 'highpass_enabled' in config:
            self.coefficients.insert(0,highpass_coefficients(config['highpass_hz']) if config['highpass_enabled'] else None)
        self.states = [[(0., 0.), (0., 0.)] for _ in self.coefficients]

    def inherit(self, old):
        # State is valid only while all upstream EQ stages match. Gain/mute/solo
        # are downstream; changing them must not reset a running equalizer.
        if not old.audible: return
        for i, (new, previous) in enumerate(zip(self.coefficients, old.coefficients)):
            if new != previous: break
            self.states[i] = list(old.states[i])

    def process(self, samples):
        if not self.audible: return np.zeros_like(samples)
        for i, coefficients in enumerate(self.coefficients):
            if coefficients is None: continue
            b0, b1, b2, a1, a2 = coefficients
            output = np.empty_like(samples)
            for channel in range(2):
                z1, z2 = self.states[i][channel]; values = []
                for x in samples[:, channel].tolist():
                    y = b0*x+z1
                    z1 = b1*x-a1*y+z2; z2 = b2*x-a2*y
                    values.append(y)
                output[:, channel] = values
                self.states[i][channel] = (z1, z2)
            samples = output
        return samples if self.level == 1 else samples*self.level


def make_mixer(config):
    channels = config.get('mixer', mixer_defaults())
    solo_active = any(channel['solo'] for channel in channels.values())
    return {key: MixerChannel(channel, solo_active) for key, channel in channels.items()}
