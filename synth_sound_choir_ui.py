"""Editable vowel ensemble under the existing root pad."""
from PySide6.QtWidgets import QWidget,QVBoxLayout,QGridLayout,QLabel,QCheckBox
from synth_sound_knob import SoundKnob
from synth_sound_choir import choir_defaults


class ChoirControls(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent);layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0)
        hint=QLabel('A soft choir follows the root, octave and chord in Pad & space. It can play alongside the pad or on its own. Adjust level, Mute, Solo and EQ in Mixer → Choir.')
        hint.setWordWrap(True);layout.addWidget(hint)
        self.enabled=QCheckBox('Enable choir layer');layout.addWidget(self.enabled)
        grid=QGridLayout();layout.addLayout(grid);self.knobs={}
        entries=(('octave','Octave above pad',-1,1,1,'',1),('vowel','Vowel · OO → AH',0,100,1,' %',100),
                 ('detune','Ensemble detune',0,12,.5,' cents',1),('motion','Breathing',0,100,1,' %',100),
                 ('cutoff','Softness / cutoff',500,9000,50,' Hz',1),('air','Air',0,100,1,' %',100),
                 ('width','Stereo spread',0,100,1,' %',100),('reverb','Reverb send',0,100,1,' %',100))
        self.factors={key:factor for key,*_,factor in entries}
        for i,(key,title,lo,hi,step,suffix,_) in enumerate(entries):
            knob=SoundKnob(title,lo,hi,step,suffix,integer=key=='octave',log=key=='cutoff')
            knob.number.setAccessibleName('Choir '+title);knob.dial.setAccessibleName('Choir '+title+' knob')
            grid.addWidget(knob,i//3,i%3);self.knobs[key]=knob
        self.knobs['vowel'].setToolTip('Blend rounded OO and open AH vowels without changing the notes.')
        self.knobs['detune'].setToolTip('Three gently detuned singers per chord note. Zero keeps them in exact unison.')
        self.knobs['air'].setToolTip('A quiet, soft breath beneath the pitched voices.')
        self.knobs['reverb'].setToolTip('Send after the Choir channel level and EQ. Reverb decay and damping are in Pad & space.')
        layout.addStretch()

    def load(self,config):
        c=config.get('choir',choir_defaults());self.enabled.setChecked(c['enabled'])
        for key,knob in self.knobs.items():knob.setValue(c[key]*self.factors[key])

    def config(self):
        return dict(enabled=self.enabled.isChecked(),**{key:knob.value()/self.factors[key] for key,knob in self.knobs.items()})
