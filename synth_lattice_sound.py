"""Versioned color-wave instrument: visible lattice levels become note attacks.

Analysis uses the renderer's optical phase and grid, never the study name,
rendered pixels, or fixed timestamps. Each radial cell interval is one level.
"""
import math
import numpy as np

from synth_visual_sound import CONTROL_RATE, RATE

SCALES = {'pentatonic': (0,3,5,7,10), 'minor': (0,2,3,5,7,8,10),
          'dorian': (0,2,3,5,7,9,10), 'major': (0,2,4,5,7,9,11)}
CONNECTIONS = (('strum', 'First color wave → opening notes', 1.),
               ('steps', 'Second color wave → color-step notes', 1.))


def color_wave_sound():
    from synth_sound_mixer import mixer_defaults
    return dict(version=4, source='chromatic_lattice', enabled=True, output='generated',
                gain=.72, width=.65, seamless_loop=True,
                connections={key:dict(enabled=True,amount=amount) for key,_,amount in CONNECTIONS},
                voices={
                    'strum':dict(pitch=82.4069,pitch_mode='note',scale='minor',span=24,
                                 decay=1.15,brightness=.65,character=.86,trigger=.5),
                    'steps':dict(pitch=164.8138,pitch_mode='note',scale='minor',span=24,
                                 decay=1.45,brightness=.55,character=.78,trigger=.5)},
                mixer=mixer_defaults())


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
        for field,choices in (('pitch_mode',('hz','note')),('scale',SCALES)):
            v[field]=r.get(field,v[field])
            if v[field] not in choices:raise ValueError(f'Choose a supported {field}')
        if v['pitch_mode']=='note':v['pitch']=snapped_frequency(v['pitch'],40,880)
        if type(link.get('enabled')) is not bool:raise ValueError('Connection must be a checkbox')
        out['connections'][key]=dict(enabled=link['enabled'],amount=number(link.get('amount'),key,0,2))
    out['mixer']=normalize_mixer(raw.get('mixer',out['mixer']),number)
    return out


def lattice_sample(p,seconds,preset):
    from synth_lattice import lattice_frame,wave_distance,pulse_size,color_wave_phase
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
    for level in np.unique(levels):
        members=(levels==level)&visible
        if not members.any():continue
        # Curved/band waves group cells into one-cell-wide distance intervals.
        d=float(np.mean(distance[members]));area=float(np.mean(radii[members]**2))*4
        phase=float(color_wave_phase(d,t/p['color_period']+p['color_phase'],p))
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
    t=np.maximum(age,0);brightness=settings['brightness'];decay=settings['decay'];character=settings['character']
    harmonic=np.arange(1,19)
    stretch=(.000035 if voice=='steps' else .000003)*(1+2*character)
    frequency=hz*harmonic*np.sqrt(1+stretch*harmonic*harmonic)
    keep=frequency<RATE*.45;harmonic=harmonic[keep];frequency=frequency[keep]
    if voice=='strum':
        amplitude=np.sin(math.pi*harmonic*.21)/(harmonic**(1.05+.5*(1-brightness)))
        damping=(.55+harmonic*(.16+.28*(1-brightness)))/decay
    else:
        amplitude=np.where(harmonic==1,1.,.8)/(harmonic**(1.15+.8*(1-brightness)))
        damping=(.55+harmonic*(.10+.22*(1-brightness)))/decay
    key=(hz,voice,character,float(age[0]),len(age))
    wave=partial_cache.get(key) if partial_cache is not None else None
    if wave is None:
        phase=np.outer(math.tau*frequency,t)
        beat=1+np.where(harmonic%2,1,-1)*.0007
        wave=.78*np.sin(phase)+.22*np.sin(phase*beat[:,None])
        if partial_cache is not None:partial_cache[key]=wave
    result=np.sum(amplitude[:,None]*np.exp(-np.outer(damping,t))*wave,axis=0)
    # The visual gesture defines the note order, not an acoustic instrument.
    # Higher morph settings use a closing FM spectrum: an elastic, metallic
    # opening and a hollow/glassy second voice, both retaining a pitched core.
    carrier=math.tau*hz*t;ratio=2.005 if voice=='strum' else 3.005
    depth=(1.2+4.5*brightness)*np.exp(-t/(decay*(.16+.22*brightness)))
    depth=np.minimum(depth,max(0.,(RATE*.42/hz-1)/ratio-1))
    modulation=depth*np.sin(carrier*ratio)
    synth=(.82*np.sin(carrier+modulation)+.18*np.sin(carrier*1.0015+modulation*.7))
    synth*=1.12*np.exp(-t*.55/decay)
    result=result*(1-character)+synth*character
    attack=.003 if voice=='strum' else .007
    a=np.clip(t/attack,0,1);a=a*a*(3-2*a)
    tail=np.clip((6*decay-t)/.04,0,1);tail=tail*tail*(3-2*tail)
    return result*a*tail*(age>=0)


class ColorWaveVoice:
    def __init__(self,sequence,config,signals,*,warm_loop=True):
        from synth_sound_mixer import make_mixer
        from synth_sound_loop import cyclic_notes
        self.config=config;self.signals=signals;self.total=round(sequence['duration']*RATE)
        self.looping=config['seamless_loop'];self.states=[];self.mixer=make_mixer(config)
        self.notes=color_notes(signals,config)
        if self.looping:self.notes=cyclic_notes(self.notes,self.total/RATE,lambda n:6*config['voices'][n['voice']]['decay'])
        self.starts=np.array([n['time'] for n in self.notes]);self.max_tail=6*max(v['decay'] for v in config['voices'].values())
        has_eq=any(any(c is not None for c in channel.coefficients) for channel in self.mixer.values())
        if warm_loop and self.looping and has_eq:self.render(-round(.75*RATE),round(.75*RATE))

    def render(self,start,length,*,tone_cache=None):
        pieces=[]
        while length:
            local=start%self.total if self.looping else start
            count=min(length,self.total-local) if self.looping else length
            pieces.append(self._render(local,count,tone_cache));start+=count;length-=count
        return np.concatenate(pieces) if pieces else np.empty((0,2),np.float32)

    def _render(self,start,length,tone_cache):
        t=(start+np.arange(length))/RATE;c=self.config
        channels={k:np.zeros((length,2)) for k in ('strum','steps')}
        lo=np.searchsorted(self.starts,t[0]-self.max_tail);hi=np.searchsorted(self.starts,t[-1],side='right')
        for note in self.notes[lo:hi]:
            key=note['voice'];v=c['voices'][key];age=t-note['time']
            if age[0]>6*v['decay']:continue
            tone=struck_tone(age,v['pitch']*2**(note['semitones']/12),key,v,tone_cache)
            tone*=.14*note['velocity']*c['connections'][key]['amount']
            pan=note['pan']*c['width']
            channels[key][:,0]+=tone*math.sqrt((1-pan)*.5);channels[key][:,1]+=tone*math.sqrt((1+pan)*.5)
        result=self.mixer['body'].process(channels['strum'])+self.mixer['arpeggio'].process(channels['steps'])
        result=np.tanh(result)*c['gain']
        if not self.looping:
            fade=np.minimum(np.clip(t/.008,0,1),np.clip((self.total/RATE-t)/.04,0,1));result*=fade[:,None]
        return result.astype(np.float32)


def color_blocks(sequence,config,signals,cancel,block_size=RATE):
    voice=ColorWaveVoice(sequence,config,signals)
    for start in range(0,voice.total,block_size):
        cancel.check();yield voice.render(start,min(block_size,voice.total-start))
