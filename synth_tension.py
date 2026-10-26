"""Stateless elastic signal deformation, reusable on any RGB source.

Echoes reconstruct previous deformation poses of the current input frame, not
previous video frames. The bounded analytic clock makes seeks and export agree.
"""
from __future__ import annotations

import math
import numpy as np
from PIL import Image, ImageFilter

MAX_ECHOES = 5


def modules(Module, P):
    return (Module('signal_tension', 'Signal tension',
        'Pull bright source details into elastic filaments, then let them recoil. Unequal gestures leave fading impressions. Works with shapes, text and footage.', (
        P('tension', 'Tension', .72, 0, 1, .01, 'Reach of the elastic pull. Zero leaves the source intact.'),
        P('cohesion', 'Cohesion', .50, 0, 1, .01, 'How much of the original silhouette stays together during the pull. Higher values protect legibility.'),
        P('persistence', 'Persistence', 1.35, 0, 4, .05, 'Seconds of fading deformation poses. Uses the current source image, not previous video frames. Zero removes echoes.'),
        P('instability', 'Instability', .60, 0, 1, .01, 'Disorder within the filaments and the damped recoil. Timing variation independently changes gesture spacing.'),
        P('texture', 'Texture', .32, 0, 1, .01, 'Fine moving grain and broken light within the pulled signal. Leaves the background alone.'),
        P('direction', 'Pull direction', -12., -180, 180, 1, '0 pulls horizontally; 90 vertically.'),
        P('spacing', 'Filament spacing', 8., 3, 32, .5, 'Pixels at a 720-pixel artwork edge.'),
        P('bend', 'Filament bend', .55, 0, 1, .01, 'Curvature of individual threads as they stretch away from the form.'),
        P('period', 'Gesture interval', 4.6, 1.5, 20, .1, 'Average seconds between pulls at global speed 1.'),
        P('timing', 'Timing variation', .75, 0, 1, .01, 'Unequal anticipation, hold and release durations. Zero repeats the same timing.'),
        P('variation', 'Gesture variation', 0., 0, 1, .01, 'Change the strength, direction, filament shape and recovery of each pull. Zero preserves the original gesture.'),
        P('flutter', 'Filament flutter', 0., 0, 1, .01, 'Small irregular movements within the threads as they pull and recover. Does not shake the whole canvas.'),
        P('phase', 'Starting phase', 0., 0, 1, .01),
        P('palette', 'Filament palette', 1, 0, 3, 1, choices=('Source colors', 'Copper / ice', 'Violet / acid', 'Silver / phosphor')),
        P('color', 'Filament color', .70, 0, 1, .01, 'Color added to pulled details and residual impressions. Zero retains the source colors.'),
        P('glow', 'Filament glow', .32, 0, 1, .01),
        P('region', 'Affected region', 0, 0, 1, 1, choices=('Highlights', 'Whole image')),
        P('threshold', 'Highlight threshold', .24, 0, .9, .01, 'Brightness above which the source joins the filaments.'),
        P('softness', 'Selection softness', .18, .01, .5, .01),
    )),)


def _smooth(x):
    x = np.clip(x, 0., 1.)
    return x*x*x*(x*(x*6-15)+10)


def _random(seed, index, lane):
    # Stable integer hash, independent of NumPy RNG state and render order.
    x = (int(seed) ^ (int(index)*0x9e3779b1) ^ (lane*0x85ebca6b)) & 0xffffffff
    x ^= x >> 16; x = x*0x7feb352d & 0xffffffff
    x ^= x >> 15; x = x*0x846ca68b & 0xffffffff
    return ((x ^ (x >> 16)) & 0xffffffff)/0xffffffff


def _legacy_gesture(p, seconds, seed):
    """Continuous anticipation, sharply accelerating pull, then damped release."""
    clock = max(0., seconds)/p['period'] + p['phase']
    nominal = math.floor(clock)
    # Jittered cell boundaries remain monotonic, avoiding an accumulating clock.
    def boundary(i):
        return i + (.20*(2*_random(seed,i,1)-1)*p['timing'] if i > 0 else 0.)
    index = max(0, nominal)
    if clock < boundary(index): index -= 1
    elif clock >= boundary(index+1): index += 1
    start, end = boundary(index), boundary(index+1)
    u = (clock-start)/(end-start)
    hold = .22 + .15*p['timing']*_random(seed,index,2)
    peak = hold + .22 + .10*p['timing']*_random(seed,index,3)
    release = peak + .06 + .04*p['timing']*_random(seed,index,4)
    if u < hold:
        strength = -.06*math.sin(math.pi*u/hold)**2
    elif u < peak:
        strength = float(_smooth((u-hold)/(peak-hold)))
    elif u < release:
        strength = 1.
    else:
        v = (u-release)/(1-release)
        strength = (1-float(_smooth(min(1.,v*2.1))))
        strength -= .23*p['instability']*math.sin(math.pi*v*3)*math.exp(-v*5)*math.sin(math.pi*v)
    amplitude = 1-p['timing']*.28*_random(seed,index,5)
    # Direction changes only while the motion has returned to zero at a boundary.
    sign = 1. if _random(seed,index,6) > .5 else -1.
    return strength*amplitude, sign


def _gesture_cell(p, seconds, seed):
    clock = max(0., seconds)/p['period'] + p['phase']
    amount = p.get('variation', 0.)
    def boundary(i):
        return i + ((.20+.16*amount)*(2*_random(seed,i,1)-1)*p['timing'] if i > 0 else 0.)
    index = max(0, math.floor(clock))
    if clock < boundary(index): index -= 1
    elif clock >= boundary(index+1): index += 1
    start, end = boundary(index), boundary(index+1)
    return index, (clock-start)/(end-start)


def _wander(seconds, seed, lane, rate=1.):
    """Continuous, nonperiodic drift; reproducible without playback history."""
    clock = seconds*rate
    left = math.floor(clock)
    blend = float(_smooth(clock-left))
    return 2*((1-blend)*_random(seed,left,lane)+blend*_random(seed,left+1,lane))-1


def gesture(p, seconds, seed):
    amount = p.get('variation', 0.)
    if not amount:
        return _legacy_gesture(p, seconds, seed)
    index, u = _gesture_cell(p, seconds, seed)
    r = lambda lane: _random(seed,index,lane)
    # Separate anticipation, loading, release and settling lengths. Each pull
    # gets a different peak and hesitation; no repeated fixed envelope.
    kind = min(2, int(r(36)*3))
    phrases = ((.23,.10,.07,.04,.05,.10,.23,.18),
               (.10,.15,.24,.07,.06,.17,.13,.08),
               (.18,.10,.15,.07,.10,.12,.18,.10))
    durations = np.array(phrases[kind])
    durations *= [1+amount*(1.5*r(20+i)-.65) for i in range(8)]
    knots = np.concatenate(([0.], np.cumsum(durations)/durations.sum()))
    peak = 1+amount*(.70*r(28)-.42)
    values = [0., -.035-.065*amount*r(29), .06+.12*amount*r(30),
              peak, peak*(1-amount*(.22+.50*r(31))),
              peak*(1+amount*(.75*r(32)-.48)),
              -(.08+.27*r(33))*amount*p['instability'],
              .09*amount*p['instability']*r(34), 0.]
    if kind == 0:
        values[4:6] = (peak*.40, peak*.14)
    elif kind == 1:
        values[4:6] = (peak*(.86+.10*r(31)), peak*(.58+.20*r(32)))
    segment = min(7, max(0, int(np.searchsorted(knots,u,side='right')-1)))
    v = (u-knots[segment])/(knots[segment+1]-knots[segment])
    # Asymmetric acceleration: rapid releases coexist with slow resistance.
    power = 1+amount*(2.2*r(40+segment)-.55)
    weight = float(_smooth(np.clip(v,0,1)**power))
    strength = values[segment]+(values[segment+1]-values[segment])*weight
    # Fade in the new phrasing when the control is adjusted from zero.
    # Map the old envelope into the same cell before blending. Mixing two
    # independently jittered clocks would flip direction while still stretched.
    start=index+(.20*(2*_random(seed,index,1)-1)*p['timing'] if index else 0.)
    end=index+1+.20*(2*_random(seed,index+1,1)-1)*p['timing']
    legacy_time=(start+u*(end-start)-p['phase'])*p['period']
    legacy,_=_legacy_gesture(p,legacy_time,seed)
    sign=1. if r(6)>.5 else -1.
    return legacy*(1-amount)+strength*amount, sign


def _sample(arr, x, y):
    """Bilinear reflected sampling: a pulled full-frame source has no black seam."""
    h,w = arr.shape[:2]
    def reflect(pos, size):
        if size <= 1: return np.zeros_like(pos)
        value = np.mod(pos, 2*(size-1))
        return np.minimum(value, 2*(size-1)-value)
    x=reflect(x,w); y=reflect(y,h)
    x0=x.astype(np.int32); y0=y.astype(np.int32)
    x1=np.minimum(x0+1,w-1); y1=np.minimum(y0+1,h-1)
    fx=(x-x0).astype(np.float32)[...,None]; fy=(y-y0).astype(np.float32)[...,None]
    return ((arr[y0,x0]*(1-fx)+arr[y0,x1]*fx)*(1-fy)
            +(arr[y1,x0]*(1-fx)+arr[y1,x1]*fx)*fy).astype(np.float32)


def _blur(arr, radius):
    image=Image.fromarray(np.uint8(np.clip(arr,0,1)*255))
    return np.asarray(image.filter(ImageFilter.GaussianBlur(radius)),np.float32)/255.


def render_signal_tension(arr, p, seconds, speed, seed, reference):
    if p['tension'] <= 0: return arr
    h,w=arr.shape[:2]; edge=min(reference); unit=edge/720.
    t=max(0.,seconds*speed)
    lum=arr.max(axis=2)
    mask=np.ones_like(lum) if p['region'] else _smooth((lum-p['threshold'])/p['softness'])
    if not np.any(mask): return arr
    # Preserve a low source floor so vacated highlights retain the original dark
    # stock. This floor is zero in Whole image mode, where the full signal moves.
    floor=0. if p['region'] else np.minimum(np.min(arr,axis=(0,1)),p['threshold'])
    source=np.maximum(0.,arr-floor)*mask[...,None]
    base=arr-source
    yy,xx=np.mgrid[:h,:w].astype(np.float32)
    angle=math.radians(p['direction']); cs,sn=math.cos(angle),math.sin(angle)
    x=xx-(w-1)*.5; y=yy-(h-1)*.5
    u=(x*cs+y*sn)/edge; v=(-x*sn+y*cs)/edge
    phase=(seed%991)/991*math.tau
    pitch=max(1.,p['spacing']*unit)
    thread=.5+.5*np.sin(v*edge/pitch*math.tau + .6*np.sin(v*31+phase))
    rib=thread**6

    def deform(time):
        force,direction=gesture(p,time,seed)
        force*=p['tension']
        variation=p.get('variation',0.); flutter=p.get('flutter',0.)
        if variation or flutter:
            index,_=_gesture_cell(p,time,seed)
            r=lambda lane:_random(seed,index,lane)
            turn=angle+math.radians(variation*100*(r(60)-.5))
            dc,ds=math.cos(turn),math.sin(turn)
            du=(x*dc+y*ds)/edge; dv=(-x*ds+y*dc)/edge
            a=_wander(time,seed,70,2.7); b=_wander(time,seed,71,5.3)
            local_phase=phase+variation*math.tau*r(61)
            local_pitch=pitch*(1+variation*(r(62)-.45))
            flutter_field=(np.sin(dv*47+local_phase+a*3)
                           +.45*np.sin(dv*113-local_phase+b*2))
            thread_phase=dv*edge/local_pitch*math.tau
            thread_phase+=(1-variation)*.6*np.sin(dv*31+phase)
            thread_phase+=variation*1.3*np.sin(dv*29+local_phase)
            thread_phase+=flutter*.65*abs(force)*flutter_field
            strands=(.5+.5*np.sin(thread_phase))**(6+variation*5*r(63))
            slow=np.sin(dv*(17+variation*(14*r(64)-6))+local_phase+time*(.7-.45*variation))
            slow+=.32*np.sin(dv*(41-2*variation)-time*(.9-.5*variation)+variation*local_phase)
            disorder=(.5+.5*np.sin(dv*83+local_phase+time*.6))*p['instability']
            local_force=force*(1+flutter*.30*flutter_field)
            pull=local_force*direction*(.15*slow+strands*(.18+.27*disorder))
            stretch=1+np.abs(local_force)*(.25+strands*(1.5+disorder*2))
            su=du/stretch-pull
            bend=p['bend']*(1+variation*(1.5*r(65)-.75))
            sv=dv+local_force*bend*.065*np.sin(du*8+dv*11+time*.65*(1-variation)+variation*local_phase)*np.minimum(1.,np.abs(du)*2+.2)
            sv+=abs(force)*flutter*.004*flutter_field*np.sin(du*19+b)
            sx=(su*dc-sv*ds)*edge+(w-1)*.5
            sy=(su*ds+sv*dc)*edge+(h-1)*.5
        else:
            slow=np.sin(v*17+time*.7+phase)+.32*np.sin(v*41-time*.9)
            disorder=(.5+.5*np.sin(v*83+phase+time*.6))*p['instability']
            pull=force*direction*(.15*slow + rib*(.18+.27*disorder))
            stretch=1+abs(force)*(.25+rib*(1.5+disorder*2))
            su=u/stretch-pull
            sv=v+force*p['bend']*.065*np.sin(u*8+v*11+time*.65)*np.minimum(1.,np.abs(u)*2+.2)
            sx=(su*cs-sv*sn)*edge+(w-1)*.5
            sy=(su*sn+sv*cs)*edge+(h-1)*.5
        return _sample(source,sx,sy), abs(force)

    pulled,force=deform(t)
    # Protect a readable core while allowing separate, much longer fine threads.
    protected=p['cohesion']*.78
    live=source*protected+pulled*(1-protected)
    trace=np.zeros_like(arr)
    if p['persistence'] > 0:
        for i in range(1,MAX_ECHOES+1):
            age=i/(MAX_ECHOES+1)
            lag=age*p['persistence']
            if t < lag: continue
            echo,energy=deform(t-lag)
            trace+=echo*(energy*(1-age)**1.7*.27*float(_smooth((t-lag)/.3)))
    if p['palette']:
        colors=np.array((((1.,.44,.18),(.18,.87,1.)),
                         ((.92,.22,1.),(.71,1.,.25)),
                         ((.87,.97,1.),(.31,.94,.60))),np.float32)[int(p['palette'])-1]
        tint=colors[0]+(.5+.5*np.sin(v*8+t*.42+u*3))[...,None]*(colors[1]-colors[0])
        tintmix=p['color']*min(1.,force*1.8)
        live=live*(1-tintmix)+live.max(axis=2)[...,None]*tint*tintmix
        trace=trace*(1-p['color'])+trace.max(axis=2)[...,None]*colors[1]*p['color']
    if p['texture']:
        tick=math.floor(t*24+1e-8)
        rng=np.random.default_rng((int(seed)+tick*7919)%2**32)
        grain=rng.normal(0,.22,(h,w)).astype(np.float32)
        wear=.5+.5*np.sin(u*370+np.sin(v*150+tick*.7)*3)
        live*=np.clip(1+p['texture']*force*(grain-.3*wear),0,1.4)[...,None]
    signal=live+trace
    if p['glow']:
        # Glow only during deformation/echoes; a resting source is unchanged.
        signal+=_blur(signal,max(.35,unit*7))*p['glow']*min(1.,force+float(trace.max()))
    return np.asarray(np.clip(base+signal,0,1),np.float32)
