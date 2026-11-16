"""Blink-driven circular waves: fluid displacement or rigid cell responses."""
from functools import lru_cache

import numpy as np

from synth_lattice_eye import blink_events
from synth_lattice_relief import smooth


@lru_cache(maxsize=128)
def ripple_triggers(count, period, duration, variation, double, fps, seed):
    """Trigger at the deepest visible lid pose, skipping blinks lost to cadence."""
    p = dict(eye_blink_count=count, eye_blink_period=period,
             eye_blink_duration=duration, eye_blink_variation=variation,
             eye_double_blink=double)
    events = blink_events(p, seed)
    if not fps:
        return tuple(((start+length*.24) % period, 1.) for start, length in events)
    samples = np.arange(int(np.ceil(period*fps)), dtype=np.float64)/fps
    triggers = {}
    for start, length in events:
        q = ((samples-start) % period)/max(.001, length)
        closure = np.where(q < .24, smooth(q/.24), 1-smooth((q-.34)/.66))
        closure[q >= 1] = 0.
        i = int(np.argmax(closure))
        strength = float(closure[i])
        if strength > .01:
            trigger = float(samples[i])
            triggers[trigger] = max(triggers.get(trigger, 0.), strength)
    return tuple(sorted(triggers.items()))


def ripple_profile(p, seconds, seed=0):
    """One radial lookup per frame; independent of canvas size and render history."""
    amount = p.get('eye_ripple', 0.)
    if not amount or not p.get('eye_enabled', 0) or not p['eye_blink_count'] or not p['eye_opening']:
        return None
    period = p['eye_blink_period']
    triggers = ripple_triggers(int(p['eye_blink_count']), period, p['eye_blink_duration'],
                              p['eye_blink_variation'], p['eye_double_blink'],
                              p.get('eye_blink_fps', 0), int(seed))
    speed = p.get('eye_ripple_speed', 7.)
    reach = p.get('eye_ripple_reach', 10.)
    width = p.get('eye_ripple_width', .8)
    lifetime = (reach+3*width)/speed
    phase = (float(seconds)+p['eye_blink_phase']*period) % period
    ages = [(age, strength) for trigger, strength in triggers
            for age in np.arange((phase-trigger) % period, lifetime, period)]
    if not ages:
        return None
    radius = np.linspace(0., reach, 2049)
    response = p.get('eye_ripple_response', 0)
    if response in (1, 2):
        return cell_pulse_profile(radius, ages, p)
    if response == 3:
        fluid = (fluid_wave_profile(radius, ages, p)[1]*p.get('eye_ripple_fluid', 0.)/100.
                 if p.get('eye_ripple_fluid', 0.) else np.zeros_like(radius))
        return (*cell_pulse_profile(radius, ages, p), fluid)
    return fluid_wave_profile(radius, ages, p)


def fluid_wave_profile(radius, ages, p):
    """Original displacement, reused unchanged by the custom response mixer."""
    speed = p.get('eye_ripple_speed', 7.)
    reach = p.get('eye_ripple_reach', 10.)
    width = p.get('eye_ripple_width', .8)
    amount = p.get('eye_ripple', 0.)
    wave = np.zeros_like(radius)
    for age, strength in ages:
        front = age*speed
        z = (radius-front)/width
        packet = (1-z*z)*np.exp(-.5*z*z)
        packet *= 1-smooth(np.abs(z)-2.)  # Finite support: untouched cells stay exact.
        envelope = smooth(front/.8)*(1-smooth((front-reach)/(3*width)))
        wave += packet*strength*envelope
    # A single crest and its shallow trough spread out and lose energy. Both
    # the origin and outer limit are smooth, without moving the eye itself.
    falloff = np.exp(-radius/(reach*.65))*(1-smooth((radius/reach-.7)/.3))*smooth(radius/.8)
    limit = .18*min(1., width)
    displacement = limit*np.tanh(wave*amount*p['eye_opening'])*falloff
    return radius, displacement


def cell_pulse_profile(radius, ages, p):
    """A causal attack/release after the front reaches each cell's center.

    Unlike a fluid crest/trough, this only grows and restores a whole figure.
    It never shrinks past the original size or changes its contour.
    """
    pulse = np.zeros_like(radius)
    shake = np.zeros_like(radius)
    for age, strength in ages:
        q = (age*p['eye_ripple_speed']-radius)/p['eye_ripple_width']
        envelope = smooth(q/.24)*(1-smooth((q-.24)/.76))*strength
        pulse += envelope
        shake += envelope*np.sin(q*4*np.pi)
    reach = p['eye_ripple_reach']
    falloff = np.exp(-radius/(reach*.85))*(1-smooth((radius/reach-.7)/.3))
    amount = p['eye_ripple']*p['eye_opening']
    return radius, np.tanh(pulse*amount)*falloff, np.tanh(shake*amount)*falloff


def ripple_cells(ix, iy, u, v, radius, rounding, spacing, p, profile):
    """Scale/translate/rotate whole cells, respecting their sampling boundaries."""
    # Grid offsets affect cell centers, while the wave's origin is the eye.
    distance = np.hypot(ix+p['grid_x'], iy+p['grid_y'])
    pulse = np.interp(distance, profile[0], profile[1], right=0.)
    angle = np.deg2rad(p['rotation'])
    custom = p['eye_ripple_response'] == 3
    turn = None
    if custom:
        pulse *= p.get('eye_ripple_size', 100.)/100.
        if p.get('eye_ripple_rotation', 0.):
            vibration = np.interp(distance, profile[0], profile[2], right=0.)
            direction = np.where(np.sin(ix*2.39996323+iy*1.61803399) >= 0, 1., -1.)
            turn = np.deg2rad(p['eye_ripple_rotation'])*vibration*direction
            turn = limit_cell_rotation(turn, angle, radius, rounding, spacing, p['shape'])
            angle = angle+turn
    extent = radius
    if p['shape'] in (1, 2):
        factor = 1.
        if p['shape'] == 2:
            angle += np.pi/4
            factor = .70710678
        extent = radius*factor*((abs(np.cos(angle))+abs(np.sin(angle)))*(1-rounding)+rounding)
    # Respect the existing inter-cell space, including rotated squares. Dense
    # cells grow less; no new clipping at their fixed sampling-tile boundaries.
    room = np.maximum(0., .485*spacing-extent)
    dx = dy = 0.
    position = p.get('eye_ripple_position', 0.)/100. if custom else 1.
    if p['eye_ripple_response'] == 2 or (custom and position):
        vibration = np.interp(distance, profile[0], profile[2], right=0.)
        if custom: vibration *= position
        direction = ix*2.39996323 + iy*1.61803399
        shift = vibration*np.minimum(.035*spacing, room)
        dx, dy = shift*np.cos(direction), shift*np.sin(direction)
    available = np.maximum(1., (.485*spacing-np.maximum(np.abs(dx), np.abs(dy)))/np.maximum(extent, .001))
    scale = np.minimum(1+pulse*.20, available)
    if turn is not None:
        # Rotate sampling about the cell's own center, after its optional shake.
        dtype = u.dtype
        u, v = u-dx, v-dy
        cs, sn = np.cos(turn), np.sin(turn)
        return (u*cs+v*sn).astype(dtype), (-u*sn+v*cs).astype(dtype), (radius*scale).astype(radius.dtype)
    return (u-dx).astype(u.dtype), (v-dy).astype(v.dtype), (radius*scale).astype(radius.dtype)


def limit_cell_rotation(turn, angle, radius, rounding, spacing, shape):
    """Limit rotation of dense square cells without silently shrinking them."""
    if shape not in (1, 2):
        return turn
    factor = .70710678 if shape == 2 else 1.
    base = angle+(np.pi/4 if shape == 2 else 0.)
    # Extent of a rounded square: r * ((cos a + sin a)*(1-corner)+corner).
    limit = (.485*spacing/np.maximum(radius*factor, .001)-rounding)/np.maximum(1-rounding, 1e-6)
    half_angle = np.arcsin(np.clip(limit/np.sqrt(2), 1/np.sqrt(2), 1))-np.pi/4
    folded = (base+np.pi/4) % (np.pi/2)-np.pi/4
    safe = np.where(np.abs(folded) <= half_angle+1e-7,
                    np.clip(turn, -half_angle-folded, half_angle-folded), 0.)
    return np.where((limit >= np.sqrt(2)) | (rounding >= 1.), turn, safe)


def ripple_coordinates(x, y, center, spacing, profile):
    """Warp sampling coordinates before drawing, so no cell is clipped or resampled."""
    if profile is None:
        return x, y
    dx = (x-center[0])/spacing; dy = (y-center[1])/spacing
    radius = np.hypot(dx, dy)
    displacement = np.interp(radius, *profile, right=0.)
    scale = displacement/np.maximum(radius, 1e-6)
    return (x-dx*scale*spacing).astype(x.dtype), (y-dy*scale*spacing).astype(y.dtype)
