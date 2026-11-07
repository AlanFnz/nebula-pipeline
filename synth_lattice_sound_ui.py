"""Two playable colors, with independent tuning and timbre controls."""
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QGroupBox,QLabel,QComboBox,QCheckBox
from synth_sound_knob import SoundKnob
from synth_sound_pitch import PitchControl
from synth_lattice_sound import color_wave_sound
from synth_sound_analog import PAD_HARMONIES


class ColorWaveControls(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent);layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0)
        hint=QLabel('Each visible level plays a note, from the center outward. Opening follows the first color change; Color steps follows the second. Timing follows the visual color wave, including its speed and phase.')
        hint.setWordWrap(True);layout.addWidget(hint)
        pair=QHBoxLayout();layout.addLayout(pair);self.voices={};self.combos=[]
        for key,title in (('strum','Opening'),('steps','Color steps')):
            box=QGroupBox(title);column=QVBoxLayout(box);pair.addWidget(box)
            engine=QComboBox();engine.setAccessibleName(title+' engine')
            engine.addItem('Original partials / FM','partials');engine.addItem('Analog ensemble','analog')
            column.addWidget(engine);self.combos.append(engine)
            pitch=PitchControl('Root',40,880);pitch.set_compact(True);column.addWidget(pitch)
            for widget,label in ((pitch.number,'frequency'),(pitch.mode,'tuning'),(pitch.note,'note')):
                widget.setAccessibleName(title+' root '+label)
            scale=QComboBox();scale.setAccessibleName(title+' scale')
            for label,value in (('Natural minor','minor'),('Minor pentatonic','pentatonic'),('Dorian','dorian'),('Major','major')):scale.addItem(label,value)
            column.addWidget(scale);self.combos.append(scale)
            controls={'pitch':pitch,'scale':scale,'engine':engine}
            for fields in ((('span','Range',12,48,1,' st'),('decay','Decay',150,3000,10,' ms')),
                           (('brightness','Brightness',0,100,1,' %'),('character','Timbre morph',0,100,1,' %')),
                           (('clarity','Note clarity',0,100,1,' %'),('polyphony','Sustain voices',0,8,1,'')),
                           (('trigger','Color transition point',5,95,1,' %'),),
                           (('reverb','Reverb send',0,100,1,' %'),('delay','Delay send',0,100,1,' %'))):
                row=QHBoxLayout();column.addLayout(row)
                for field,label,lo,hi,step,suffix in fields:
                    knob=SoundKnob(label,lo,hi,step,suffix,integer=field=='polyphony');row.addWidget(knob);controls[field]=knob
                    knob.number.setAccessibleName(title+' '+label);knob.dial.setAccessibleName(title+' '+label+' knob')
            controls['span'].setToolTip('Spread the visible levels across this pitch range, snapped to the chosen scale.')
            controls['trigger'].setToolTip('Where in each color transition its note starts. 50% follows the midpoint. This changes sound timing, not the picture.')
            controls['delay'].setToolTip('Send this voice to the soft stereo echo. Adjust its time, feedback and tone in Pad & space. The pad does not enter this delay.')
            controls['character'].setToolTip('Morph from plucked or struck partials at 0% to an evolving electronic FM tone at 100%. Opening is metallic and elastic; Color steps is hollow and glassy.')
            controls['clarity'].setToolTip('Bring the fundamental forward and tune the electronic partials to harmonic ratios. Keeps the synthetic timbre while making the scale easier to hear.')
            controls['polyphony'].number.setSpecialValueText('Unlimited')
            controls['polyphony'].setToolTip('Number of notes that can sustain in this voice. Older notes release smoothly as new ones arrive; attack timing stays connected to the image. Zero preserves unlimited overlap.')
            analog_box=QGroupBox('Oscillators & filter');analog_layout=QVBoxLayout(analog_box);column.addWidget(analog_box);analog={}
            for fields in ((('wave','Saw → pulse',0,100,1,' %'),('sub','Sub oscillator',0,100,1,' %')),
                           (('unison','Unison voices',1,5,1,''),('detune','Detune',0,20,.5,' cents')),
                           (('cutoff','Filter cutoff',120,10000,20,' Hz'),('resonance','Resonance',0,85,1,' %')),
                           (('sweep','Filter envelope',0,4,.1,' oct'),('attack','Attack',3,100,1,' ms')),
                           (('drive','Saturation',0,100,1,' %'),)):
                row=QHBoxLayout();analog_layout.addLayout(row)
                for field,label,lo,hi,step,suffix in fields:
                    knob=SoundKnob(label,lo,hi,step,suffix,integer=field=='unison',log=field=='cutoff')
                    row.addWidget(knob);analog[field]=knob
                    knob.number.setAccessibleName(title+' '+label);knob.dial.setAccessibleName(title+' '+label+' knob')
            analog['wave'].setToolTip('Blend a band-limited saw with a slowly moving pulse wave.')
            analog['sweep'].setToolTip('How far the filter opens at each note attack, then settles toward Filter cutoff.')
            analog['detune'].setToolTip('Small pitch differences between oscillators add body without changing the scale.')
            controls['analog']=analog;controls['analog_box']=analog_box
            engine.currentIndexChanged.connect(self.update_engines)
            self.voices[key]=controls;column.addStretch()
        row=QHBoxLayout();layout.addLayout(row)
        self.level=SoundKnob('Master level',0,100,1,' %');self.width=SoundKnob('Stereo spread',0,100,1,' %')
        row.addWidget(self.level);row.addWidget(self.width)
        self.loop=QCheckBox('Seamless audio loop');self.loop.setToolTip('Carry note tails across the end of the timeline. The image must also form a loop.');layout.addWidget(self.loop)

    def load(self,value):
        self.level.setValue(value['gain']*100);self.width.setValue(value['width']*100);self.loop.setChecked(value['seamless_loop'])
        for key,controls in self.voices.items():
            v=value['voices'][key];controls['pitch'].load(v['pitch'],v['pitch_mode'])
            controls['engine'].setCurrentIndex(controls['engine'].findData(v['engine']))
            controls['scale'].setCurrentIndex(controls['scale'].findData(v['scale']))
            for field in ('span','decay','brightness','character','trigger','clarity','polyphony','reverb','delay'):
                factor=1000 if field=='decay' else 1 if field in ('span','polyphony') else 100
                controls[field].setValue(v[field]*factor)
            for field,knob in controls['analog'].items():knob.setValue(v['analog'][field]*analog_factor(field))
        self.update_engines()

    def update_engines(self):
        for controls in self.voices.values():
            analog=controls['engine'].currentData()=='analog';controls['analog_box'].setVisible(analog)
            for field in ('brightness','character','clarity'):controls[field].setVisible(not analog)

    def config(self):
        value=color_wave_sound();value.update(gain=self.level.value()/100,width=self.width.value()/100,seamless_loop=self.loop.isChecked())
        for key,controls in self.voices.items():
            v=value['voices'][key];v.update(pitch=controls['pitch'].value(),pitch_mode=controls['pitch'].tuning(),scale=controls['scale'].currentData(),engine=controls['engine'].currentData())
            for field in ('span','decay','brightness','character','trigger','clarity','polyphony','reverb','delay'):
                factor=1000 if field=='decay' else 1 if field in ('span','polyphony') else 100
                v[field]=controls[field].value()/factor
            v['analog']={field:knob.value()/analog_factor(field) for field,knob in controls['analog'].items()}
        return value


def analog_factor(field):
    return 1000 if field=='attack' else 100 if field in ('wave','sub','resonance','drive') else 1


class PadSpaceControls(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent);layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0)
        hint=QLabel('A soft sustained harmony under the color notes. Follow opening root tracks the melody root; choose a chord quality that fits its scale. Balance or solo the pad in Mixer.')
        hint.setWordWrap(True);layout.addWidget(hint)
        self.enabled=QCheckBox('Enable root pad');self.follow=QCheckBox('Follow opening root')
        row=QHBoxLayout();row.addWidget(self.enabled);row.addWidget(self.follow);layout.addLayout(row)
        self.pitch=PitchControl('Pad root',40,880);self.pitch.set_compact(True);layout.addWidget(self.pitch)
        self.follow.toggled.connect(lambda on:self.pitch.setEnabled(not on))
        row=QHBoxLayout();row.addWidget(QLabel('Harmony'));self.harmony=QComboBox();self.harmony.setAccessibleName('Pad harmony')
        for key,title,_ in PAD_HARMONIES:self.harmony.addItem(title,key)
        self.harmony.setToolTip('Open chords spread their notes across octaves. Minor 9 adds a minor third, fifth, seventh and ninth around the root. Root / octave preserves the original pad.')
        row.addWidget(self.harmony,1);layout.addLayout(row)
        self.pad={};self.space={};self.delay={}
        for title,entries,controls in (
                ('Root pad',(('octave','Octave',-1,2,1,''),('cutoff','Softness / cutoff',120,4000,20,' Hz'),('detune','Detune',0,20,.5,' cents'),
                             ('motion','Slow movement',0,100,1,' %'),('reverb','Reverb send',0,100,1,' %')),self.pad),
                ('Shared space',(('chorus','Stereo chorus',0,100,1,' %'),('decay','Reverb decay',.4,6,.1,' s'),
                                 ('damping','Reverb damping',0,100,1,' %')),self.space),
                ('Note delay',(('time','Time',40,1200,.5,' ms'),('feedback','Feedback',0,65,1,' %'),
                               ('tone','Tone',400,8000,20,' Hz')),self.delay)):
            box=QGroupBox(title);row=QHBoxLayout(box);layout.addWidget(box)
            for key,label,lo,hi,step,suffix in entries:
                knob=SoundKnob(label,lo,hi,step,suffix,log=key=='cutoff',integer=key=='octave');row.addWidget(knob);controls[key]=knob
                knob.number.setAccessibleName(title+' '+label);knob.dial.setAccessibleName(title+' '+label+' knob')
        self.space['chorus'].setToolTip('A slowly modulated stereo delay adds width and movement to the ensemble.')
        self.space['damping'].setToolTip('Higher damping softens the high frequencies in the reverb tail.')
        self.delay['time'].setToolTip('Time between echoes. Each voice has its own Delay send in Sound; the pad stays outside the delay.')
        self.delay['tone'].setToolTip('Low-pass filter on each repeat. Lower frequencies make the echoes softer and darker.')
        layout.addStretch()

    def load(self,value):
        p=value['pad'];self.enabled.setChecked(p['enabled']);self.follow.setChecked(p['follow_root'])
        self.pitch.load(p['pitch'],p['pitch_mode']);self.pitch.setEnabled(not p['follow_root'])
        self.harmony.setCurrentIndex(self.harmony.findData(p['harmony']))
        for key,knob in self.pad.items():knob.setValue(p[key]*(100 if key in ('motion','reverb') else 1))
        for key,knob in self.space.items():knob.setValue(value['space'][key]*(1 if key=='decay' else 100))
        for key,knob in self.delay.items():knob.setValue(value['delay'][key]*delay_factor(key))

    def config(self):
        pad=dict(enabled=self.enabled.isChecked(),follow_root=self.follow.isChecked(),pitch=self.pitch.value(),pitch_mode=self.pitch.tuning(),harmony=self.harmony.currentData())
        pad.update({key:knob.value()/(100 if key in ('motion','reverb') else 1) for key,knob in self.pad.items()})
        space={key:knob.value()/(1 if key=='decay' else 100) for key,knob in self.space.items()}
        delay={key:knob.value()/delay_factor(key) for key,knob in self.delay.items()}
        return dict(pad=pad,space=space,delay=delay)


def delay_factor(key):
    return 1000 if key=='time' else 100 if key=='feedback' else 1
