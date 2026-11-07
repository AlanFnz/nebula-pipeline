"""Two playable colors, with independent tuning and timbre controls."""
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QGroupBox,QLabel,QComboBox,QCheckBox
from synth_sound_knob import SoundKnob
from synth_sound_pitch import PitchControl
from synth_lattice_sound import color_wave_sound


class ColorWaveControls(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent);layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0)
        hint=QLabel('Each visible level plays a note, from the center outward. Opening follows the first color change; Color steps follows the second. Timing follows the visual color wave, including its speed and phase.')
        hint.setWordWrap(True);layout.addWidget(hint)
        pair=QHBoxLayout();layout.addLayout(pair);self.voices={};self.combos=[]
        for key,title in (('strum','Opening'),('steps','Color steps')):
            box=QGroupBox(title);column=QVBoxLayout(box);pair.addWidget(box)
            pitch=PitchControl('Root',40,880);pitch.set_compact(True);column.addWidget(pitch)
            for widget,label in ((pitch.number,'frequency'),(pitch.mode,'tuning'),(pitch.note,'note')):
                widget.setAccessibleName(title+' root '+label)
            scale=QComboBox();scale.setAccessibleName(title+' scale')
            for label,value in (('Natural minor','minor'),('Minor pentatonic','pentatonic'),('Dorian','dorian'),('Major','major')):scale.addItem(label,value)
            column.addWidget(scale);self.combos.append(scale)
            controls={'pitch':pitch,'scale':scale}
            for fields in ((('span','Range',12,48,1,' st'),('decay','Decay',150,3000,10,' ms')),
                           (('brightness','Brightness',0,100,1,' %'),('character','Timbre morph',0,100,1,' %')),
                           (('trigger','Color transition point',5,95,1,' %'),)):
                row=QHBoxLayout();column.addLayout(row)
                for field,label,lo,hi,step,suffix in fields:
                    knob=SoundKnob(label,lo,hi,step,suffix);row.addWidget(knob);controls[field]=knob
                    knob.number.setAccessibleName(title+' '+label);knob.dial.setAccessibleName(title+' '+label+' knob')
            controls['span'].setToolTip('Spread the visible levels across this pitch range, snapped to the chosen scale.')
            controls['trigger'].setToolTip('Where in each color transition its note starts. 50% follows the midpoint. This changes sound timing, not the picture.')
            controls['character'].setToolTip('Morph from plucked or struck partials at 0% to an evolving electronic FM tone at 100%. Opening is metallic and elastic; Color steps is hollow and glassy.')
            self.voices[key]=controls;column.addStretch()
        row=QHBoxLayout();layout.addLayout(row)
        self.level=SoundKnob('Master level',0,100,1,' %');self.width=SoundKnob('Stereo spread',0,100,1,' %')
        row.addWidget(self.level);row.addWidget(self.width)
        self.loop=QCheckBox('Seamless audio loop');self.loop.setToolTip('Carry note tails across the end of the timeline. The image must also form a loop.');layout.addWidget(self.loop)

    def load(self,value):
        self.level.setValue(value['gain']*100);self.width.setValue(value['width']*100);self.loop.setChecked(value['seamless_loop'])
        for key,controls in self.voices.items():
            v=value['voices'][key];controls['pitch'].load(v['pitch'],v['pitch_mode'])
            controls['scale'].setCurrentIndex(controls['scale'].findData(v['scale']))
            for field in ('span','decay','brightness','character','trigger'):
                factor=1000 if field=='decay' else 1 if field=='span' else 100
                controls[field].setValue(v[field]*factor)

    def config(self):
        value=color_wave_sound();value.update(gain=self.level.value()/100,width=self.width.value()/100,seamless_loop=self.loop.isChecked())
        for key,controls in self.voices.items():
            v=value['voices'][key];v.update(pitch=controls['pitch'].value(),pitch_mode=controls['pitch'].tuning(),scale=controls['scale'].currentData())
            for field in ('span','decay','brightness','character','trigger'):
                factor=1000 if field=='decay' else 1 if field=='span' else 100
                v[field]=controls[field].value()/factor
        return value
