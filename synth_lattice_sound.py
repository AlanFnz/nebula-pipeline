"""Versioned color-wave instrument: visible lattice levels become note attacks.

Analysis uses the renderer's optical phase and grid, never the study name,
rendered pixels, or fixed timestamps. Each radial cell interval is one level.
"""
import math
import copy
import json
import threading
from collections import OrderedDict
import numpy as np

from synth_visual_sound import CONTROL_RATE, RATE
from synth_sound_analog import analog_defaults,pad_defaults,space_defaults,PAD_HARMONIES

COLOR_CHANNELS=(('body','Opening'),('arpeggio','Color steps'),('pad','Root pad'))
_ROOM_CACHE=OrderedDict()
_ROOM_LOCK=threading.Lock()

SCALES = {'pentatonic': (0,3,5,7,10), 'minor': (0,2,3,5,7,8,10),
          'dorian': (0,2,3,5,7,9,10), 'major': (0,2,4,5,7,9,11)}
CONNECTIONS = (('strum', 'First color wave → opening notes', 1.),
               ('steps', 'Second color wave → color-step notes', 1.))


def color_wave_sound():
    from synth_sound_mixer import mixer_defaults
    out=dict(version=4, source='chromatic_lattice', enabled=True, output='generated',
                gain=.72, width=.65, seamless_loop=True,
                connections={key:dict(enabled=True,amount=amount) for key,_,amount in CONNECTIONS},
                voices={
                    'strum':dict(pitch=82.4069,pitch_mode='note',scale='minor',span=24,
                                 decay=.22,brightness=.65,character=.86,trigger=.5,clarity=1.,polyphony=1),
                    'steps':dict(pitch=164.8138,pitch_mode='note',scale='minor',span=24,
                                 decay=.32,brightness=.55,character=.78,trigger=.5,clarity=1.,polyphony=1)},
                mixer=mixer_defaults(COLOR_CHANNELS),pad=pad_defaults(),space=space_defaults())
    out['mixer']['pad']['level_db']=-22.
    for v in out['voices'].values():v.update(engine='partials',analog=analog_defaults(),reverb=0.)
    return out


def normalize_color_wave(raw):
    from synth_sound_sequence import snapped_frequency
    from synth_sound_mixer import normalize_mixer
    out=color_wave_sound()
    if raw.get('source',out['source'])!=out['source']:raise ValueError('Color-wave sound needs Chromatic lattice')
    def number(value,key,low,high):
        if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value) or not low<=value<=high:
            raise ValueError(f'{key} must be between {low} and {high}')
        return float(value)
    for key in ('enabled','seamless_loop'):
        v=raw.get(key,out[key])
        if type(v) is not bool:raise ValueError(f'{key} must be a checkbox')
        out[key]=v
    out['output']=raw.get('output',out['output'])
    if out['output'] not in ('generated','existing','silent'):raise ValueError('Choose an audio output')
    for key in ('gain','width'):out[key]=number(raw.get(key,out[key]),key,0,1)
    voices=raw.get('voices',out['voices'])
    links=raw.get('connections',out['connections'])
    if not isinstance(voices,dict) or set(voices)!=set(out['voices']):raise ValueError('Color waves need Opening and Color steps voices')
    if not isinstance(links,dict) or set(links)!=set(out['connections']):raise ValueError('Color waves need both visual connections')
    for key,v in out['voices'].items():
        r=voices[key];link=links[key]
        if not isinstance(r,dict) or not isinstance(link,dict):raise ValueError('Invalid color-wave voice')
        for field,lo,hi in (('pitch',40,880),('span',12,48),('decay',.15,3.),('brightness',0,1),('character',0,1),('trigger',.05,.95)):
            v[field]=number(r.get(field,v[field]),field,lo,hi)
        # Existing v4 documents retain their original spectral/overlap behavior.
        v['clarity']=number(r.get('clarity',0.),'Note clarity',0,1)
        count=r.get('polyphony',0)
        if isinstance(count,bool) or not isinstance(count,(int,float)) or not math.isfinite(count) or count!=int(count) or not 0<=count<=8:
            raise ValueError('Sustain voices must be an integer between 0 and 8')
        v['polyphony']=int(count)
        v['engine']=r.get('engine','partials')
        if v['engine'] not in ('partials','analog'):raise ValueError('Choose a supported voice engine')
        v['reverb']=number(r.get('reverb',0.),'Reverb send',0,1)
        analog=r.get('analog',analog_defaults())
        if not isinstance(analog,dict):raise ValueError('Invalid analog voice')
        for field,lo,hi in (('wave',0,1),('unison',1,5),('detune',0,20),('sub',0,1),('cutoff',120,10000),
                            ('resonance',0,.85),('sweep',0,4),('attack',.003,.1),('drive',0,1)):
            v['analog'][field]=number(analog.get(field,v['analog'][field]),field,lo,hi)
        if v['analog']['unison']!=int(v['analog']['unison']):raise ValueError('Unison must be a whole number')
        v['analog']['unison']=int(v['analog']['unison'])
        for field,choices in (('pitch_mode',('hz','note')),('scale',SCALES)):
            v[field]=r.get(field,v[field])
            if v[field] not in choices:raise ValueError(f'Choose a supported {field}')
        if v['pitch_mode']=='note':v['pitch']=snapped_frequency(v['pitch'],40,880)
        if type(link.get('enabled')) is not bool:raise ValueError('Connection must be a checkbox')
        out['connections'][key]=dict(enabled=link['enabled'],amount=number(link.get('amount'),key,0,2))
    pad=raw.get('pad',pad_defaults());space=raw.get('space',space_defaults())
    if not isinstance(pad,dict) or not isinstance(space,dict):raise ValueError('Invalid pad or space settings')
    for key in ('enabled','follow_root'):
        value=pad.get(key,out['pad'][key])
        if type(value) is not bool:raise ValueError('Pad '+key+' must be a checkbox')
        out['pad'][key]=value
    for key,lo,hi in (('pitch',40,880),('cutoff',120,4000),('detune',0,20),('motion',0,1),('reverb',0,1)):
        out['pad'][key]=number(pad.get(key,out['pad'][key]),'Pad '+key,lo,hi)
    octave=number(pad.get('octave',1),'Pad octave',-1,2)
    if octave!=int(octave):raise ValueError('Pad octave must be a whole number')
    out['pad']['octave']=int(octave)
    harmony=pad.get('harmony','root')
    if harmony not in tuple(key for key,_,_ in PAD_HARMONIES):raise ValueError('Choose a supported pad harmony')
    out['pad']['harmony']=harmony
    out['pad']['pitch_mode']=pad.get('pitch_mode','note')
    if out['pad']['pitch_mode'] not in ('hz','note'):raise ValueError('Choose pad tuning')
    if out['pad']['pitch_mode']=='note':out['pad']['pitch']=snapped_frequency(out['pad']['pitch'],40,880)
    for key,lo,hi in (('chorus',0,1),('decay',.4,6),('damping',0,1)):
        out['space'][key]=number(space.get(key,out['space'][key]),'Space '+key,lo,hi)
    raw_mixer=raw.get('mixer',out['mixer'])
    if isinstance(raw_mixer,dict) and 'pad' not in raw_mixer:raw_mixer=dict(raw_mixer,pad=out['mixer']['pad'])
    out['mixer']=normalize_mixer(raw_mixer,number,COLOR_CHANNELS)
    return out


def lattice_sample(p,seconds,preset):
    from synth_lattice import lattice_frame,wave_distance,pulse_size,color_wave_phase,phrase_period,phrase_levels
    w,h=preset['width'],preset['height']
    (cx,cy),spacing,_=lattice_frame(p,(w,h),preset)
    ix=np.arange(math.ceil(-cx/spacing-.5),math.floor((w-cx)/spacing+.5)+1)
    iy=np.arange(math.ceil(-cy/spacing-1),math.floor((h-cy)/spacing)+1)+.5
    x,y=np.meshgrid(ix,iy)
    distance=np.abs(wave_distance(x,y,p));levels=np.floor(distance+1e-8).astype(int)
    t=seconds*preset.get('speed',1.)
    radii=.5*p['size']*pulse_size(distance,t,p)
    visible=((cx+x*spacing+radii*spacing)>0)&((cx+x*spacing-radii*spacing)<w)
    visible&=((cy+y*spacing+radii*spacing)>0)&((cy+y*spacing-radii*spacing)<h)
    result={}
    level_count=phrase_levels(p,preset) if p.get('color_rhythm',0) else 16
    for level in np.unique(levels):
        members=(levels==level)&visible
        if not members.any():continue
        # Curved/band waves group cells into one-cell-wide distance intervals.
        d=float(np.mean(distance[members]));area=float(np.mean(radii[members]**2))*4
        phase=float(color_wave_phase(d,t/phrase_period(p)+p['color_phase'],p,level_count))
        result[int(level)]=(phase,area*p['mix']*min(1.,p['light']))
    return result


def lattice_signals(sequence,cancel):
    from synth_sequence import normalize_sequence,resolve_sequence_frame
    from synth_audio_reactivity import apply_reactivity
    from synth_performance import apply_signals
    seq=normalize_sequence(sequence);times=np.arange(math.ceil(seq['duration']*CONTROL_RATE)+1)/CONTROL_RATE
    records=[];levels=set();states={};cache={}
    for i,seconds in enumerate(times):
        if i%24==0:cancel.check()
        _,t,clock,_,_,_,_,base=resolve_sequence_frame(seq,min(seconds,seq['duration']-1e-9),normalized=True,state_cache=states)
        if 'audio_reactivity' in seq:base=apply_reactivity(base,seq,t,cancel=cancel)
        entry=next((m for m in base['modules'] if m['id']=='chromatic_lattice' and m['enabled']),None)
        record={}
        if entry and entry['params']['mix']>0:
            p=entry['params'];key=(tuple(sorted(p.items())),clock,base['width'],base['height'],base.get('speed'),repr(base.get('reference')),base.get('framing'),base.get('object_x'),base.get('object_y'))
            if key not in cache:
                if len(cache)>512:cache.clear()
                cache[key]=lattice_sample(p,clock,base)
            record=cache[key]
        records.append(record);levels.update(record)
    zeros=np.zeros(len(times));signals=dict(time=times,presence=zeros.copy(),expansion=zeros.copy(),motion=zeros.copy(),opening=zeros.copy())
    for level in sorted(levels):
        phases=np.array([r.get(level,(0.,0.))[0] for r in records])
        areas=np.array([r.get(level,(0.,0.))[1] for r in records])
        signals[f'lattice_phase_{level}']=phases;signals[f'lattice_area_{level}']=areas
        signals['presence']=np.maximum(signals['presence'],areas)
    signals['expansion']=signals['presence'].copy()
    return apply_signals(signals,seq.get('visual_performance'),seq['duration'],seq['fps'])


def color_notes(signals,config):
    times=signals['time'];levels=sorted(int(k.rsplit('_',1)[1]) for k in signals if k.startswith('lattice_phase_'))
    notes=[]
    if not config['enabled']:return notes
    for voice,(begin,end) in (('strum',(0.,.12)),('steps',(.32,.38))):
        settings=config['voices'][voice];connection=config['connections'][voice]
        if not connection['enabled'] or connection['amount']==0:continue
        threshold=begin+(end-begin)*settings['trigger']
        scale=[octave*12+n for octave in range(5) for n in SCALES[settings['scale']] if octave*12+n<=settings['span']]
        for rank,level in enumerate(levels):
            phase=signals[f'lattice_phase_{level}'];area=signals[f'lattice_area_{level}']
            crossed=np.flatnonzero(np.floor(phase[1:]-threshold)>np.floor(phase[:-1]-threshold))+1
            for i in crossed:
                # A returning source clock is not a strum. Nor is enabling an
                # offscreen/absent cell; it must actually cross a color phase.
                delta=phase[i]-phase[i-1]
                if delta<=0 or delta>.25 or min(area[i-1],area[i])<.002:continue
                target=math.floor(phase[i]-threshold)+threshold
                at=times[i-1]+(times[i]-times[i-1])*(target-phase[i-1])/delta
                degree=round(rank*(len(scale)-1)/max(1,len(levels)-1))
                notes.append(dict(time=float(at),voice=voice,level=level,semitones=scale[degree],
                                  velocity=.70+.22*min(1,math.sqrt(area[i])),pan=-.5+rank/max(1,len(levels)-1)))
    return sorted(notes,key=lambda n:(n['time'],n['level']))


def color_activity(signals,config):
    times=signals['time'];out={k:np.zeros_like(times) for k in ('strum','steps')}
    for note in color_notes(signals,config):
        age=times-note['time'];envelope=np.where(age>=0,np.exp(-np.maximum(age,0)/.18),0.)
        out[note['voice']]=np.maximum(out[note['voice']],envelope)
    return out


def struck_tone(age,hz,voice,settings,partial_cache=None):
    """Morph damped partials into evolving FM tones, with smooth attacks/tails."""
    t=np.maximum(age,0);brightness=settings['brightness'];decay=settings['decay'];character=settings['character'];clarity=settings.get('clarity',0.)
    harmonic=np.arange(1,19)
    stretch=(.000035 if voice=='steps' else .000003)*(1+2*character)*(1-clarity)
    frequency=hz*harmonic*np.sqrt(1+stretch*harmonic*harmonic)
    keep=frequency<RATE*.45;harmonic=harmonic[keep];frequency=frequency[keep]
    if voice=='strum':
        amplitude=np.sin(math.pi*harmonic*.21)/(harmonic**(1.05+.5*(1-brightness)))
        damping=(.55+harmonic*(.16+.28*(1-brightness)))/decay
    else:
        amplitude=np.where(harmonic==1,1.,.8)/(harmonic**(1.15+.8*(1-brightness)))
        damping=(.55+harmonic*(.10+.22*(1-brightness)))/decay
    key=(hz,voice,character,clarity,float(age[0]),len(age))
    wave=partial_cache.get(key) if partial_cache is not None else None
    if wave is None:
        phase=np.outer(math.tau*frequency,t)
        beat=1+np.where(harmonic%2,1,-1)*.0007*(1-clarity)
        wave=.78*np.sin(phase)+.22*np.sin(phase*beat[:,None])
        if partial_cache is not None:partial_cache[key]=wave
    result=np.sum(amplitude[:,None]*np.exp(-np.outer(damping,t))*wave,axis=0)
    # The visual gesture defines the note order, not an acoustic instrument.
    # Higher morph settings use a closing FM spectrum: an elastic, metallic
    # opening and a hollow/glassy second voice, both retaining a pitched core.
    carrier=math.tau*hz*t;ratio=(2. if voice=='strum' else 3.)+.005*(1-clarity)
    depth=(1.2+4.5*brightness)*np.exp(-t/(decay*(.16+.22*brightness)))
    depth=np.minimum(depth,max(0.,(RATE*.42/hz-1)/ratio-1))
    modulation=depth*np.sin(carrier*ratio)
    synth=(.82*np.sin(carrier+modulation)+.18*np.sin(carrier*(1+.0015*(1-clarity))+modulation*.7))
    synth*=1.12*np.exp(-t*.55/decay)
    result=result*(1-character)+synth*character
    fundamental=1.12*np.sin(carrier)*np.exp(-t*.55/decay)
    result=result*(1-.55*clarity)+fundamental*(.55*clarity)
    attack=.003 if voice=='strum' else .007
    a=np.clip(t/attack,0,1);a=a*a*(3-2*a)
    tail=np.clip((6*decay-t)/.04,0,1);tail=tail*tail*(3-2*tail)
    return result*a*tail*(age>=0)


def articulate_notes(notes,config,period,looping):
    """Limit overlapping tails without changing any visual attack time."""
    result=[]
    for key,settings in config['voices'].items():
        voice=[n for n in notes if n['voice']==key and n['time']<period]
        count=settings.get('polyphony',0)
        for i,note in enumerate(voice):
            n=dict(note,duration=6*settings['decay'])
            if count and (looping or i+count<len(voice)):
                at=i+count
                end=voice[at%len(voice)]['time']+(at//len(voice))*period
                n['gate']=end-note['time'];n['duration']=min(n['duration'],n['gate']+.02)
            result.append(n)
    return sorted(result,key=lambda n:(n['time'],n['level']))


class ColorWaveVoice:
    def __init__(self,sequence,config,signals,*,warm_loop=True,warm_cache_only=False,cancel=None):
        from synth_sound_mixer import make_mixer
        from synth_sound_loop import cyclic_notes
        self.config=config;self.signals=signals;self.total=round(sequence['duration']*RATE)
        self.looping=config['seamless_loop'];self.states=[];self.mixer=make_mixer(config)
        self.analog=any(v['engine']=='analog' for v in config['voices'].values()) or config['pad']['enabled']
        from synth_sound_analog import StereoSpace
        self.ambience=bool(config['space']['chorus'] or config['pad']['enabled'] and config['pad']['reverb']
                           or any(v['reverb'] for v in config['voices'].values()))
        self.space=StereoSpace(config['space'],self.total/RATE if self.looping else None) if self.ambience else None
        self.notes=articulate_notes(color_notes(signals,config),config,self.total/RATE,self.looping)
        if self.looping:self.notes=cyclic_notes(self.notes,self.total/RATE,lambda n:n['duration'])
        self.starts=np.array([n['time'] for n in self.notes]);self.max_tail=max((n['duration'] for n in self.notes),default=0.)
        has_eq=any(any(c is not None for c in channel.coefficients) for channel in self.mixer.values())
        if warm_loop and self.looping and (has_eq or self.ambience):
            cache_key=json.dumps((self.total,config,self.notes),sort_keys=True) if self.ambience else None
            if cache_key:
                with _ROOM_LOCK:
                    cached=_ROOM_CACHE.get(cache_key)
                    if cached is not None:
                        self.space,self.mixer=copy.deepcopy(cached);_ROOM_CACHE.move_to_end(cache_key);return
                # A new draft may have no prepared room yet. Bloom naturally
                # rather than blocking the live producer behind a long preroll.
                if warm_cache_only:return
            # Prime the room from preceding turns, including wrapped note tails.
            # Live edits transfer this state instead of recomputing it.
            history=max(.75,config['space']['decay']*3) if self.ambience else .75
            samples=round(history*RATE)
            for start in range(-samples,0,2048):
                if cancel:cancel.check()
                self.render(start,min(2048,-start))
            if cache_key:
                with _ROOM_LOCK:
                    _ROOM_CACHE[cache_key]=copy.deepcopy((self.space,self.mixer))
                    while len(_ROOM_CACHE)>4:_ROOM_CACHE.popitem(last=False)

    def inherit(self,old):
        if self.space is not None and getattr(old,'space',None) is not None:self.space.inherit(old.space)

    def render(self,start,length,*,tone_cache=None):
        pieces=[]
        while length:
            local=start%self.total if self.looping else start
            count=min(length,self.total-local) if self.looping else length
            if self.analog or self.ambience:count=min(count,1024)
            pieces.append(self._render(local,count,tone_cache));start+=count;length-=count
        return np.concatenate(pieces) if pieces else np.empty((0,2),np.float32)

    def _render(self,start,length,tone_cache):
        from synth_sound_analog import analog_note,root_pad
        t=(start+np.arange(length))/RATE;c=self.config
        if not c['enabled']:return np.zeros((length,2),np.float32)
        channels={k:np.zeros((length,2)) for k in ('strum','steps')}
        lo=np.searchsorted(self.starts,t[0]-self.max_tail);hi=np.searchsorted(self.starts,t[-1],side='right')
        for note in self.notes[lo:hi]:
            key=note['voice'];v=c['voices'][key];age=t-note['time']
            if age[0]>note['duration']:continue
            hz=v['pitch']*2**(note['semitones']/12)
            if v['engine']=='analog':tone=analog_note(age,hz,v)
            else:tone=struck_tone(age,hz,key,v,tone_cache)
            if 'gate' in note:
                release=np.clip((note['gate']+.02-age)/.02,0,1)
                envelope=release*release*(3-2*release)
                tone*=envelope[:,None] if tone.ndim==2 else envelope
            tone*=.14*note['velocity']*c['connections'][key]['amount']
            pan=note['pan']*c['width']
            if tone.ndim==2:
                mid=tone.mean(axis=1,keepdims=True);tone=mid+(tone-mid)*c['width']
                channels[key]+=tone*np.array([math.sqrt(1-pan),math.sqrt(1+pan)])
            else:
                channels[key][:,0]+=tone*math.sqrt((1-pan)*.5);channels[key][:,1]+=tone*math.sqrt((1+pan)*.5)
        opening=self.mixer['body'].process(channels['strum']);steps=self.mixer['arpeggio'].process(channels['steps'])
        result=opening+steps;send=opening*c['voices']['strum']['reverb']+steps*c['voices']['steps']['reverb']
        if c['pad']['enabled'] and self.mixer['pad'].audible:
            hz=c['voices']['strum']['pitch'] if c['pad']['follow_root'] else c['pad']['pitch']
            period=self.total/RATE if self.looping else None
            cache_key=('pad',start,length,hz,period,tuple(sorted(c['pad'].items())))
            pad=tone_cache.get(cache_key) if tone_cache is not None else None
            if pad is None:
                pad=root_pad(t,hz,c['pad'],period)*.34
                if tone_cache is not None:tone_cache[cache_key]=pad
            if tone_cache is not None:pad=pad.copy()
            if not self.looping:pad*=np.minimum(np.clip(t/.8,0,1),np.clip((self.total/RATE-t)/.8,0,1))[:,None]
            pad=self.mixer['pad'].process(pad);result+=pad;send+=pad*c['pad']['reverb']
        if self.space is not None:result=self.space.process(result,send,start)
        result=np.tanh(result)*c['gain']
        if not self.looping:
            fade=np.minimum(np.clip(t/.008,0,1),np.clip((self.total/RATE-t)/.04,0,1));result*=fade[:,None]
        return result.astype(np.float32)


def color_blocks(sequence,config,signals,cancel,block_size=RATE):
    voice=ColorWaveVoice(sequence,config,signals)
    for start in range(0,voice.total,block_size):
        cancel.check();yield voice.render(start,min(block_size,voice.total-start))
