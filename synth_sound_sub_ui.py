"""Independent low-end layer; pitch follows the pad automatically."""
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QCheckBox
from synth_sound_knob import SoundKnob
from synth_sound_sequence import frequency_note,note_name
from synth_sound_sub import sub_defaults,sub_frequency


class SubControls(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent);layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0)
        hint=QLabel('A deep, steady tone follows the pad root, even when the pad is muted. It stays centered and dry, outside chorus, reverb and delay. Balance it in Mixer → Sub bass.')
        hint.setWordWrap(True);layout.addWidget(hint)
        self.enabled=QCheckBox('Enable sub bass layer');layout.addWidget(self.enabled)
        self.pitch_label=QLabel();self.pitch_label.setAccessibleName('Sub bass resulting pitch');layout.addWidget(self.pitch_label)
        row=QHBoxLayout();layout.addLayout(row);self.knobs={}
        entries=(('octaves_below','Octaves below pad',1,4,1,''),
                 ('body','Harmonic body',0,100,1,' %'),('cutoff','Low-pass cutoff',40,800,5,' Hz'))
        for key,title,lo,hi,step,suffix in entries:
            knob=SoundKnob(title,lo,hi,step,suffix,integer=key=='octaves_below',log=key=='cutoff')
            knob.number.setAccessibleName('Sub bass '+title);knob.dial.setAccessibleName('Sub bass '+title+' knob')
            self.knobs[key]=knob;row.addWidget(knob)
        self.knobs['octaves_below'].setToolTip('Same pitch class as the pad, in a lower register. The resulting frequency is shown above.')
        self.knobs['body'].setToolTip('Zero is a pure sine. Raise for soft, tuned harmonics that make the bass more audible on small speakers.')
        self.knobs['cutoff'].setToolTip('12 dB/octave low-pass on Sub bass only. Lower values soften the harmonics and may also reduce the fundamental.')
        layout.addStretch()

    def load(self,config):
        c=config.get('sub',sub_defaults());self.enabled.setChecked(c['enabled'])
        for key,knob in self.knobs.items():knob.setValue(c[key]*(100 if key=='body' else 1))

    def update_pitch(self,root,pad_octave):
        hz=sub_frequency(root,pad_octave,self.config())
        suffix=' · below 20 Hz' if hz<20 else ''
        self.pitch_label.setText(f'{note_name(frequency_note(hz))} · {hz:.2f} Hz{suffix}')

    def config(self):
        return dict(enabled=self.enabled.isChecked(),**{key:knob.value()/(100 if key=='body' else 1) for key,knob in self.knobs.items()})
