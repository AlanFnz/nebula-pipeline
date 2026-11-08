"""Independent chime overlay, triggered by the first visible color wave."""
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QLabel,QCheckBox,QComboBox
from synth_sound_knob import SoundKnob
from synth_sound_pitch import PitchControl
from synth_sound_chimes import chime_layer_defaults


class ChimeLayerControls(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent);layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0)
        hint=QLabel('An extra metallic cascade follows the first color wave alongside Opening. Tune it here; adjust its level, high-pass filter, Mute, Solo and EQ in Mixer → Chimes.')
        hint.setWordWrap(True);layout.addWidget(hint)
        self.enabled=QCheckBox('Enable chimes layer');layout.addWidget(self.enabled)
        self.pitch=PitchControl('Chimes root',40,1760);self.pitch.set_compact(True);layout.addWidget(self.pitch)
        for widget,label in ((self.pitch.number,'frequency'),(self.pitch.mode,'tuning'),(self.pitch.note,'note')):
            widget.setAccessibleName('Chimes root '+label)
        row=QHBoxLayout();row.addWidget(QLabel('Scale'));self.scale=QComboBox();row.addWidget(self.scale,1);layout.addLayout(row)
        self.scale.setAccessibleName('Chimes scale')
        for title,key in (('Natural minor','minor'),('Minor pentatonic','pentatonic'),('Dorian','dorian'),('Major','major')):self.scale.addItem(title,key)
        row.addWidget(QLabel('Resonance'));self.tuning=chime_tuning_combo('Chimes');row.addWidget(self.tuning,1)
        grid=QGridLayout();layout.addLayout(grid);self.knobs={}
        entries=(('span','Range',12,48,1,' st',1),('decay','Decay',150,3000,10,' ms',1000),
                 ('brightness','Brightness',0,100,1,' %',100),('shimmer','Shimmer',0,100,1,' %',100),
                 ('strike','Soft strike',2,40,1,' ms',1000),('polyphony','Sustain voices',0,8,1,'',1),
                 ('trigger','Color transition point',5,95,1,' %',100),('reverb','Reverb send',0,100,1,' %',100),
                 ('delay','Delay send',0,100,1,' %',100))
        self.factors={key:factor for key,*_,factor in entries}
        for i,(key,title,lo,hi,step,suffix,_) in enumerate(entries):
            knob=SoundKnob(title,lo,hi,step,suffix,integer=key=='polyphony');self.knobs[key]=knob;grid.addWidget(knob,i//3,i%3)
            knob.number.setAccessibleName('Chimes '+title);knob.dial.setAccessibleName('Chimes '+title+' knob')
        self.knobs['polyphony'].number.setSpecialValueText('Unlimited')
        self.knobs['polyphony'].setToolTip('How many tubes can ring together. Unlimited preserves every tail; smaller values release older notes smoothly.')
        self.knobs['trigger'].setToolTip('Note attacks follow the first color change independently of the Opening voice. Change this point without changing the image.')
        self.knobs['span'].setToolTip('Spread the visible levels across this many semitones, within the chosen scale.')
        self.knobs['shimmer'].setToolTip('Gentle beating between metallic resonances. Does not move the note attacks.')
        self.knobs['strike'].setToolTip('Soften the start of each struck tube.')
        for key in ('reverb','delay'):self.knobs[key].setToolTip('Send after the Chimes channel level, high-pass and EQ. Shared space and echo settings are in Pad & space.')
        layout.addStretch()

    def load(self,config):
        v=config.get('chime_layer',chime_layer_defaults());self.enabled.setChecked(v['enabled'])
        self.pitch.load(v['pitch'],v['pitch_mode']);self.scale.setCurrentIndex(self.scale.findData(v['scale']))
        self.tuning.setCurrentIndex(self.tuning.findData(v['chimes'].get('tuning','metallic')))
        for key,knob in self.knobs.items():knob.setValue((v['chimes'][key] if key in ('shimmer','strike') else v[key])*self.factors[key])

    def config(self):
        v=chime_layer_defaults();v.update(enabled=self.enabled.isChecked(),pitch=self.pitch.value(),pitch_mode=self.pitch.tuning(),scale=self.scale.currentData())
        v['chimes']['tuning']=self.tuning.currentData()
        for key,knob in self.knobs.items():
            target=v['chimes'] if key in ('shimmer','strike') else v
            target[key]=knob.value()/self.factors[key]
        return v


def chime_tuning_combo(title):
    combo=QComboBox();combo.setAccessibleName(title+' resonance tuning')
    combo.addItem('Metallic · original','metallic');combo.addItem('Harmonic · tuned','harmonic')
    combo.setToolTip('Harmonic tunes the metal resonances to multiples of each note and keeps its fundamental exact. Metallic retains the original inharmonic tubes. Shimmer adds gentle beating to upper resonances.')
    return combo
