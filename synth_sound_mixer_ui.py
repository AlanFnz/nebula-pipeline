"""Independent drone/arpeggio channel strips for the layered instrument."""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QCheckBox, QLabel
from PySide6.QtCore import Signal
from synth_sound_knob import SoundKnob
from synth_sound_mixer import CHANNELS, BANDS


class SoundMixer(QWidget):
    toggled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0)
        hint = QLabel('Balance the Drone and Arpeggio. Each has its own EQ. Both then pass through the shared Drive and visual Filter in Sound.')
        hint.setWordWrap(True); layout.addWidget(hint);self.hint=hint;self.default_hint=hint.text()
        strips = QGridLayout(); layout.addLayout(strips);self.strips=strips;self.channels = {};self.boxes={};self.color_wave=False
        for index,(key, title) in enumerate((*CHANNELS,('pad','Root pad'),('wave','Wave sine'),('chimes','Chimes'),('choir','Choir'),('sub','Sub bass'))):
            box = QGroupBox(title); column = QVBoxLayout(box)
            strips.addWidget(box,index//2,index%2)
            self.boxes[key]=box
            controls = {}; top = QHBoxLayout(); column.addLayout(top)
            level = SoundKnob('Level', -60, 6, .5, ' dB'); controls['level_db'] = level
            level.number.setAccessibleName(title+' level'); level.dial.setAccessibleName(title+' level knob')
            level.setToolTip('Channel level before the shared Drive and Filter. 0 dB preserves the original balance. Use Mute for silence.')
            top.addWidget(level); switches = QVBoxLayout(); top.addLayout(switches)
            for field, label in (('mute', 'Mute'), ('solo', 'Solo'), ('eq_enabled', 'EQ on')):
                control = QCheckBox(label); control.setAccessibleName(title+' '+label)
                controls[field] = control; switches.addWidget(control); control.toggled.connect(self.toggled)
            controls['solo'].setToolTip('Hear this channel on its own. Multiple Solo buttons play those channels together. Mute takes priority.')
            if key=='chimes':
                hp=QHBoxLayout();column.addLayout(hp)
                enabled=QCheckBox('High-pass on');enabled.setAccessibleName('Chimes high-pass enabled')
                cutoff=SoundKnob('High-pass cutoff',20,18000,10,' Hz',log=True)
                cutoff.number.setAccessibleName('Chimes high-pass frequency');cutoff.dial.setAccessibleName('Chimes high-pass frequency knob')
                cutoff.setToolTip('Remove frequencies below this cutoff at 12 dB/octave, before EQ, reverb and delay. Independent of EQ on. Type Hz or turn the knob while listening.')
                hp.addWidget(cutoff);hp.addWidget(enabled);controls.update(highpass_enabled=enabled,highpass_hz=cutoff)
                enabled.toggled.connect(cutoff.setEnabled);enabled.toggled.connect(self.toggled)
            eq = QWidget(); grid = QGridLayout(eq); grid.setContentsMargins(0, 0, 0, 0); grid.setSpacing(2); column.addWidget(eq)
            for index, (band, name, _, low, high) in enumerate(BANDS):
                gain = SoundKnob(name, -18, 18, .5, ' dB')
                frequency = SoundKnob('Frequency', low, high, 10, ' Hz', log=True)
                frequency.dial.hide()
                frequency.setToolTip('Type the frequency below the gain knob. The EQ setting is retained while EQ is off.')
                for field, knob, row in ((band+'_db', gain, 0), (band+'_hz', frequency, 1)):
                    knob.setMinimumWidth(90); knob.number.setFixedWidth(100)
                    knob.number.setAccessibleName(f'{title} {name} '+('gain' if row==0 else 'frequency'))
                    knob.dial.setAccessibleName(knob.number.accessibleName()+' knob')
                    controls[field] = knob; grid.addWidget(knob, row, index)
                gain.setToolTip('Broad bell EQ, Q 0.8.' if band=='mid' else 'Low shelf EQ.' if band=='low' else 'High shelf EQ.')
            controls['eq_enabled'].toggled.connect(eq.setEnabled)
            column.addStretch(); self.channels[key] = controls
        foot = QLabel('0 dB = unchanged · Solo isolates a channel · EQ off keeps your settings. Channel controls are saved and exported; Listen level below only changes monitoring.')
        foot.setWordWrap(True); layout.addWidget(foot); layout.addStretch()
        for key in ('pad','wave','chimes','choir','sub'):self.boxes[key].hide()

    def set_color_wave(self,active):
        self.color_wave=active
        for key in ('pad','wave','chimes','choir','sub'):self.boxes[key].setVisible(active)
        order=('body','chimes','arpeggio','wave','pad','choir','sub') if active else tuple(self.boxes)
        for box in self.boxes.values():self.strips.removeWidget(box)
        for index,key in enumerate(order):self.strips.addWidget(self.boxes[key],index//2,index%2)
        self.hint.setText('Each layer has independent level, Mute, Solo and EQ. Shape the voices in their tabs; reverb sends follow channel levels. Sub bass stays mono and dry.' if active else self.default_hint)
        for key,title in (('body','Opening' if active else 'Drone'),('arpeggio','Color steps' if active else 'Arpeggio')):
            self.boxes[key].setTitle(title)
            self.channels[key]['level_db'].setToolTip('Independent channel level after EQ.' if active else 'Channel level before the shared Drive and Filter. 0 dB preserves the original balance. Use Mute for silence.')
            for field,control in self.channels[key].items():
                name=title+' '+field.replace('_',' ')
                if isinstance(control,QCheckBox):control.setAccessibleName(name)
                else:control.number.setAccessibleName(name);control.dial.setAccessibleName(name+' knob')

    def load(self, config):
        for key, controls in self.channels.items():
            if key not in config:continue
            for field, control in controls.items():
                if isinstance(control, QCheckBox): control.setChecked(config[key][field])
                else: control.setValue(config[key][field])
            if key=='chimes':controls['highpass_hz'].setEnabled(controls['highpass_enabled'].isChecked())

    def config(self):
        return {key: {field: control.isChecked() if isinstance(control, QCheckBox) else control.value()
                      for field, control in controls.items()} for key, controls in self.channels.items() if key not in ('pad','wave','chimes','choir','sub') or self.color_wave}
