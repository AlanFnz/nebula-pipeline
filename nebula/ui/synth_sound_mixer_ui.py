"""Channel levels, monitoring switches and EQ for the layered instruments."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QGridLayout, QGroupBox, QLabel, QVBoxLayout, QWidget

from nebula.audio.synth_sound_mixer import BANDS, CHANNELS
from nebula.ui.synth_sound_knob import SoundKnob


def band_grid(parent):
    grid = QGridLayout(parent)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(6)
    grid.setVerticalSpacing(3)
    for index in range(len(BANDS)):
        grid.setColumnStretch(index, 1)
    return grid


class SoundMixer(QWidget):
    toggled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('soundMixer')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.default_hint = 'Balance the Drone and Arpeggio. Each has its own EQ. Both then pass through the shared Drive and visual Filter in Sound.'
        self.hint = QLabel(self.default_hint)
        self.hint.setObjectName('mixerHint')
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)

        self.strips = QGridLayout()
        self.strips.setSpacing(8)
        self.strips.setColumnStretch(0, 1)
        self.strips.setColumnStretch(1, 1)
        layout.addLayout(self.strips)
        self.channels = {}
        self.boxes = {}
        self.color_wave = False
        layers = (*CHANNELS, ('pad', 'Root pad'), ('wave', 'Wave sine'), ('chimes', 'Chimes'),
                  ('choir', 'Choir'), ('sub', 'Sub bass'))
        for index, (key, title) in enumerate(layers):
            controls = {}
            self.channels[key] = controls
            box = QGroupBox(title)
            self.boxes[key] = box
            self.strips.addWidget(box, index // 2, index % 2)
            column = QVBoxLayout(box)
            column.setContentsMargins(6, 8, 6, 6)
            column.setSpacing(8)

            top = band_grid(None)
            column.addLayout(top)
            level = SoundKnob('Level', -60, 6, .5, ' dB', compact=True)
            controls['level_db'] = level
            level.number.setAccessibleName(title + ' level')
            level.dial.setAccessibleName(title + ' level knob')
            level.setToolTip('Channel level before the shared Drive and Filter. 0 dB preserves the original balance. Use Mute for silence.')
            top.addWidget(level, 0, 0)
            switches = QVBoxLayout()
            switches.setSpacing(4)
            switches.addStretch()
            top.addLayout(switches, 0, 1, 1, 2)
            for field, label in (('mute', 'Mute'), ('solo', 'Solo'), ('eq_enabled', 'EQ on')):
                control = QCheckBox(label)
                control.setAccessibleName(title + ' ' + label)
                controls[field] = control
                switches.addWidget(control)
                control.toggled.connect(self.toggled)
            switches.addStretch()
            controls['solo'].setToolTip('Hear this channel on its own. Multiple Solo buttons play those channels together. Mute takes priority.')

            eq = QWidget()
            eq.setObjectName('mixerBands')
            grid = band_grid(eq)
            column.addWidget(eq)
            for band_index, (band, name, _, low, high) in enumerate(BANDS):
                gain = SoundKnob(name, -18, 18, .5, ' dB', compact=True)
                frequency = SoundKnob('Frequency', low, high, 10, ' Hz', log=True, compact=True)
                frequency.dial.hide()
                frequency.setToolTip('Type the frequency below the gain knob. The EQ setting is retained while EQ is off.')
                for field, knob, row in ((band + '_db', gain, 0), (band + '_hz', frequency, 1)):
                    knob.number.setAccessibleName(f'{title} {name} ' + ('gain' if row == 0 else 'frequency'))
                    knob.dial.setAccessibleName(knob.number.accessibleName() + ' knob')
                    controls[field] = knob
                    grid.addWidget(knob, row, band_index)
                gain.setToolTip('Broad bell EQ, Q 0.8.' if band == 'mid' else 'Low shelf EQ.' if band == 'low' else 'High shelf EQ.')
            controls['eq_enabled'].toggled.connect(eq.setEnabled)

            if key == 'chimes':
                hp = band_grid(None)
                column.addLayout(hp)
                enabled = QCheckBox('High-pass on')
                enabled.setAccessibleName('Chimes high-pass enabled')
                cutoff = SoundKnob('High-pass cutoff', 20, 18000, 10, ' Hz', log=True, compact=True)
                cutoff.number.setAccessibleName('Chimes high-pass frequency')
                cutoff.dial.setAccessibleName('Chimes high-pass frequency knob')
                cutoff.setToolTip('Remove frequencies below this cutoff at 12 dB/octave, before EQ, reverb and delay. Independent of EQ on. Type Hz or turn the knob while listening.')
                hp.addWidget(cutoff, 0, 0)
                hp.addWidget(enabled, 0, 1, 1, 2)
                controls.update(highpass_enabled=enabled, highpass_hz=cutoff)
                enabled.toggled.connect(cutoff.setEnabled)
                enabled.toggled.connect(self.toggled)
            column.addStretch(1)
            if key not in ('body', 'arpeggio'):
                box.hide()

        self.foot = QLabel('0 dB = unchanged · Solo isolates a channel · EQ off keeps your settings. Channel controls are saved and exported; Listen level below only changes monitoring.')
        self.foot.setObjectName('mixerHint')
        self.foot.setWordWrap(True)
        layout.addWidget(self.foot)
        layout.addStretch()

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
