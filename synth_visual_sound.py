"""Deterministic, one-way synthesis from effective visual motion.

Version 1: one pleated-field voice. No media assets or study-name branches.
Controls use a fixed 120 Hz clock, PCM uses 48 kHz, and preview/export use the
same complete WAV. Seeking therefore cannot change oscillator/filter history.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import wave

import numpy as np

from media import Cancellation

RATE = 48000
CONTROL_RATE = 120
VERSION = 1  # The original electric/tape instrument remains reproducible.
CONNECTIONS = (
    ('body', 'Expansion → tonal body', 1.),
    ('friction', 'Movement → friction', .65),
    ('return', 'Reopening → resonant attack', .75),
)
ACID_CONNECTIONS = (
    ('body', 'Expansion → triangle voice', 1.),
    ('filter', 'Movement → filter opening', 1.),
    ('arpeggio', 'Gestures → short arpeggios', .85),
)


def acid_sound():
    return dict(version=2, enabled=True, output='generated', source='pleated_field',
                gain=.7, pitch=146.83, pitch_mode='hz', smoothing=.10,
                cutoff=280., sweep=4200., resonance=.74, arp_rate=1., scale='pentatonic',
                connections={key: dict(enabled=True, amount=value) for key, _, value in ACID_CONNECTIONS})


def sound_connections(config):
    if config['version']==3:
        return (('body','Expansion → oscillator body',1.),*ACID_CONNECTIONS[1:])
    return ACID_CONNECTIONS if config['version'] >= 2 else CONNECTIONS


def instrument_sound():
    """A layered instrument; earlier sound contracts remain selectable."""
    out=acid_sound()
    out.update(version=3,opening=.35,density=.65,drive=.32,unison=3,detune=8.,width=.6,
               resonance=.62,smoothing=.14,attack=.022,release=.20,continuity=0.,
               arp_pitch=out['pitch'],arp_notes=4,arp_steps=0,arp_pattern='visual')
    out['oscillators']=[
        dict(id='osc1',enabled=True,wave='triangle',level=1.,transpose=0,detune=0.),
        dict(id='osc2',enabled=True,wave='saw',level=.32,transpose=0,detune=5.),
        dict(id='osc3',enabled=True,wave='triangle',level=.22,transpose=12,detune=-4.),
    ]
    from synth_sound_sequence import sequence_defaults
    out.update(sequence_defaults(), pitch_mode='hz', arp_pitch_mode='hz')
    return out


def default_sound():
    return dict(version=VERSION, enabled=True, output='generated', source='pleated_field',
                gain=.7, pitch=62., pitch_mode='hz', smoothing=.07,
                connections={key: dict(enabled=True, amount=value) for key, _, value in CONNECTIONS})


def normalize_sound(raw):
    if not isinstance(raw, dict) or type(raw.get('version')) is not int or raw['version'] not in (1, 2, 3):
        raise ValueError('Unsupported generated sound version')
    out = {1:default_sound,2:acid_sound,3:instrument_sound}[raw['version']]()
    if raw.get('source', out['source']) != 'pleated_field':
        raise ValueError('Generated sound currently supports Pleated field')
    for key in ('enabled',):
        value = raw.get(key, out[key])
        if not isinstance(value, bool): raise ValueError(f'Generated sound {key} must be a checkbox')
        out[key] = value
    out['output'] = raw.get('output', out['output'])
    if out['output'] not in ('generated', 'existing', 'silent'):
        raise ValueError('Choose generated sound, existing audio, or silence')
    def number(value, key, low, high):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f'Generated sound {key} must be between {low} and {high}')
        return float(value)
    for key, low, high in (('gain',0.,1.), ('pitch',65.,440.) if out['version']>=2 else ('pitch',35.,180.), ('smoothing',.01,.5)):
        out[key] = number(raw.get(key, out[key]), key, low, high)
    from synth_sound_sequence import snapped_frequency, normalize_sequence_controls
    out['pitch_mode'] = raw.get('pitch_mode', 'hz')
    if out['pitch_mode'] not in ('hz', 'note'): raise ValueError('Choose frequency or note tuning')
    if out['pitch_mode'] == 'note':
        low, high = (65., 440.) if out['version'] >= 2 else (35., 180.)
        out['pitch'] = snapped_frequency(out['pitch'], low, high)
    if out['version'] >= 2:
        for key, low, high in (('cutoff',80.,1800.), ('sweep',200.,12000.), ('resonance',0.,1.), ('arp_rate',.5,2.)):
            out[key] = number(raw.get(key,out[key]),key,low,high)
        if out['sweep'] < out['cutoff']: raise ValueError('Filter open frequency must be at least its closed frequency')
        out['scale'] = raw.get('scale',out['scale'])
        if out['scale'] not in ('pentatonic','minor','dorian'): raise ValueError('Choose a supported arpeggio scale')
    if out['version']==3:
        # Old documents shared a root. Capture it as the independent melody root
        # on load; changing the body pitch afterwards must not retune the melody.
        out['arp_pitch']=number(raw.get('arp_pitch',out['pitch']),'arpeggio pitch',65.,440.)
        out['arp_pitch_mode'] = raw.get('arp_pitch_mode', 'hz')
        if out['arp_pitch_mode'] not in ('hz', 'note'): raise ValueError('Choose frequency or note tuning')
        if out['arp_pitch_mode'] == 'note': out['arp_pitch'] = snapped_frequency(out['arp_pitch'], 65., 440.)
        out.update(normalize_sequence_controls(raw, number))
        for key,low,high in (('arp_notes',1,8),('arp_steps',0,16)):
            value=raw.get(key,out[key])
            if type(value) is not int or not low<=value<=high:
                raise ValueError(f'Generated sound {key} must be an integer between {low} and {high}')
            out[key]=value
        out['arp_pattern']=raw.get('arp_pattern',out['arp_pattern'])
        if out['arp_pattern'] not in ('visual','up','down','up_down'):
            raise ValueError('Choose a supported arpeggio pattern')
        for key,low,high in (('opening',0.,1.),('continuity',0.,1.),('density',0.,1.),('drive',0.,1.),('detune',0.,35.),('width',0.,1.),('attack',.012,.15),('release',.06,.6)):
            out[key]=number(raw.get(key,out[key]),key,low,high)
        out['unison']=raw.get('unison',out['unison'])
        if type(out['unison']) is not int or not 1<=out['unison']<=5: raise ValueError('Unison must use 1–5 voices')
        oscillators=raw.get('oscillators',out['oscillators'])
        if not isinstance(oscillators,list) or len(oscillators)!=3: raise ValueError('The instrument needs three oscillator slots')
        validated=[]
        for index,osc in enumerate(oscillators):
            if not isinstance(osc,dict) or osc.get('id')!=f'osc{index+1}': raise ValueError('Invalid oscillator identity')
            if type(osc.get('enabled')) is not bool: raise ValueError('Oscillator enabled must be a checkbox')
            if osc.get('wave') not in ('sine','triangle','saw','square'): raise ValueError('Choose a supported oscillator waveform')
            if type(osc.get('transpose')) is not int or not -24<=osc['transpose']<=24: raise ValueError('Oscillator tuning must be -24 to +24 semitones')
            validated.append(dict(id=osc['id'],enabled=osc['enabled'],wave=osc['wave'],transpose=osc['transpose'],
                                  level=number(osc.get('level'),'oscillator level',0.,1.),detune=number(osc.get('detune'),'oscillator detune',-50.,50.)))
        out['oscillators']=validated
    definitions = sound_connections(out)
    connections = raw.get('connections', out['connections'])
    if not isinstance(connections, dict) or set(connections) != {item[0] for item in definitions}:
        raise ValueError('Generated sound needs its three named connections')
    for key, _, _ in definitions:
        entry = connections[key]
        if not isinstance(entry, dict) or not isinstance(entry.get('enabled'), bool):
            raise ValueError('Sound connection enabled must be a checkbox')
        out['connections'][key] = dict(enabled=entry['enabled'], amount=number(entry.get('amount'), key, 0., 2.))
    return out


def audio_output(sequence):
    config = sequence.get('generated_sound') if sequence else None
    if config and config['output'] != 'existing':
        return config['output'] if config['enabled'] else 'silent'
    track = sequence.get('soundtrack') if sequence else None
    return track['export_audio'] if track else 'footage'


def _pleated_sample(params, seconds, preset):
    """Actual camera, surface clock and optical gate from the image renderer.

    A fixed probe grid samples the internal gate; it never reads finished pixels
    and is independent of monitor/export detail. No duplicate animation logic.
    """
    from synth_pleated import pleated_clock, pleated_frame, pleated_surface, field_alpha
    p = params
    t = pleated_clock(p, seconds, preset)
    w,h = preset['width'],preset['height']
    (cx,cy),unit = pleated_frame(p,(w,h),preset)
    yy,xx = np.mgrid[0:12,0:16].astype(np.float32)
    x = ((xx+.5)*w/16-cx)/max(1.,unit)
    y = ((yy+.5)*h/12-cy)/max(1.,unit)
    _,_,z,_,u,v,valid=pleated_surface(x,y,p,t)
    presence=float(np.mean(field_alpha(u,v,z,valid,unit,p)))*p['mix']
    # Coordinates are the resolved camera/flow state, not UI slider deltas.
    pose=[math.log2(p['size']), *[math.radians(p[k]) for k in ('angle','yaw','pitch')],
          (p['pan_x']+t*p['flow']+p['phase'])*.35,p['pan_y']*.35]
    return presence, pose


def visual_signals(sequence, cancel=None):
    from synth_sequence import normalize_sequence, resolve_sequence_frame
    from synth_audio_reactivity import apply_reactivity
    seq = normalize_sequence(sequence)
    cancel = cancel or Cancellation()
    count = math.ceil(seq['duration']*CONTROL_RATE)+1
    times = np.arange(count)/CONTROL_RATE
    presence = np.zeros(count); expansion=np.zeros(count); poses=np.zeros((count,6))
    enabled = np.zeros(count, dtype=bool)
    states = {}; probes = {}
    for i,seconds in enumerate(times):
        if i % 24 == 0: cancel.check()
        _,t,effect_time,_,_,_,_,base = resolve_sequence_frame(seq,min(seconds,seq['duration']-1e-9),normalized=True,state_cache=states)
        if 'audio_reactivity' in seq: base=apply_reactivity(base,seq,t,cancel=cancel)
        entry=next((m for m in base['modules'] if m['id']=='pleated_field'),None)
        if entry is None or not entry['enabled'] or entry['params']['mix']<=0: continue
        p=entry['params'];enabled[i]=True
        from synth_pleated import pleated_clock
        clock=pleated_clock(p,effect_time,base)
        key=(tuple(sorted(p.items())),base['width'],base['height'],repr(base.get('reference')),base.get('framing'),
             base.get('object_x'),base.get('object_y'),clock if p['flow'] or p['irregularity'] else 0.)
        if key not in probes:
            if len(probes)>=512: probes.clear()
            probes[key]=_pleated_sample(p,effect_time,base)
        presence[i],poses[i]=probes[key]
        expansion[i]=np.clip((poses[i,0]+1.5)/4.,0,1)
    # Backward differences keep deliberate cuts at their authored time.
    delta=np.diff(poses,axis=0,prepend=poses[:1])
    valid=enabled & np.r_[False,enabled[:-1]]
    # Spread stepped camera deltas before compression. Clipping each isolated
    # delta would turn every 12-fps gesture into an equally loud machine pulse.
    velocity=_smooth(np.linalg.norm(delta,axis=1)*CONTROL_RATE*valid,.06)
    speed=np.tanh(velocity/3.)*enabled
    events=np.zeros(count);armed=False;last=-10.
    for i,seconds in enumerate(times):
        if presence[i]<.025: armed=True
        if armed and presence[i]>.12 and enabled[i] and seconds-last>.4:
            events[i]=1.;armed=False;last=seconds
    return dict(time=times,presence=presence,expansion=expansion,motion=speed,opening=events)


def _smooth(values, seconds):
    coefficient=1-math.exp(-1/(CONTROL_RATE*seconds))
    result=np.empty_like(values);last=0.
    for i,value in enumerate(values):
        last+=coefficient*(value-last);result[i]=last
    return result


def pcm_blocks(sequence, cancel=None, *, signals=None):
    """Yield bounded stereo float blocks; phase, filter and RNG history persist.

    The entire timeline is reconstructed from zero, including partial exports.
    Audio tails stay inside the timeline, with a 45 ms edge fade. Clip loops
    follow compiled visual clocks while the oscillator remains continuous.
    """
    cancel=cancel or Cancellation();cancel.check()
    config=normalize_sound(sequence.get('generated_sound',default_sound()))
    signals=visual_signals(sequence,cancel) if signals is None else signals
    if config['version'] == 3:
        from synth_visual_sound_instrument import instrument_blocks
        yield from instrument_blocks(sequence,config,signals,cancel)
        return
    if config['version'] == 2:
        from synth_visual_sound_acid import acid_blocks
        yield from acid_blocks(sequence,config,signals,cancel)
        return
    total=round(sequence['duration']*RATE)
    gate=_smooth(signals['presence'],.025)
    expansion=_smooth(signals['expansion'],config['smoothing'])
    motion=_smooth(signals['motion'],config['smoothing'])
    attack=np.zeros(len(gate));last=0.
    for i,event in enumerate(signals['opening']):
        last=last*math.exp(-1/(CONTROL_RATE*.24))+event;attack[i]=min(1.,last)
    attack=_smooth(attack,.012)
    connections=config['connections']
    amounts={key:entry['amount'] if config['enabled'] and entry['enabled'] else 0. for key,entry in connections.items()}
    rng=np.random.default_rng(int(sequence['seed'])+90571)
    # Short FIR tape hiss; deterministic overlap carries across block boundaries.
    kernel=np.hanning(33);kernel/=np.sqrt(np.sum(kernel**2))
    history=np.zeros(32);phase=0.
    for start in range(0,total,RATE):
        cancel.check();length=min(RATE,total-start)
        times=(start+np.arange(length))/RATE
        g,e,m,a=[np.interp(times,signals['time'],values) for values in (gate,expansion,motion,attack)]
        frequency=config['pitch']*2**((.62*e+.12*m)*amounts['body'])
        phases=phase+np.cumsum(frequency)*(math.tau/RATE)
        phase=phases[-1]%math.tau
        body=(np.sin(phases)+(.12+.24*e)*np.sin(2*phases+.18*m*np.sin(3*phases))+
              .09*e*np.sin(3*phases))*(.20+.12*e)*amounts['body']
        noise=rng.standard_normal(length)
        joined=np.r_[history,noise];history=joined[-32:]
        filtered=np.convolve(joined,kernel,mode='valid')
        friction=filtered*(.012+.20*m)*amounts['friction']
        strike=(np.sin(phases*2)+.28*np.sin(phases*5))*a*.25*amounts['return']
        mono=(body+friction+strike)*g
        # Gentle saturation bounds peaks; no normalizing away an authored gain.
        mono=np.tanh(mono*1.3)*.72*config['gain']
        fade=np.minimum(np.clip(times/.045,0,1),np.clip((total/RATE-times)/.045,0,1))
        mono*=fade
        # Small movement-correlated stereo spread, with a stable center body.
        side=filtered*m*g*.035*amounts['friction']*config['gain']*fade
        yield np.stack((mono+side,mono-side),axis=1).clip(-.95,.95).astype(np.float32)


def write_sound(sequence, destination, cancel=None, *, signals=None):
    """Atomic 48 kHz / 24-bit WAV; optional generated data stays in the JSON."""
    cancel=cancel or Cancellation();cancel.check()
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.nebula-sound-',suffix='.wav',dir=destination.parent);os.close(fd)
    try:
        with wave.open(name,'wb') as output:
            output.setparams((2,3,RATE,0,'NONE','not compressed'))
            for block in pcm_blocks(sequence,cancel,signals=signals):
                integer=np.rint(block.astype(np.float64)*8388607).astype('<i4').reshape(-1)
                packed=integer.view(np.uint8).reshape(-1,4)[:,:3].tobytes()
                output.writeframesraw(packed)
        cancel.check();os.replace(name,destination)
    finally:
        Path(name).unlink(missing_ok=True)
    return destination


def sound_key(sequence):
    payload=copy.deepcopy(sequence)
    # Name/monitor FPS cannot affect sound. Authored cues retain their timing.
    payload.pop('name',None);payload.pop('fps',None)
    if payload.get('audio_reactivity') and payload.get('soundtrack'):
        path=Path(payload['soundtrack']['path'])
        try:
            stat=path.stat();payload['_audio_file']=(stat.st_size,stat.st_mtime_ns)
        except OSError: payload['_audio_file']='missing'
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
