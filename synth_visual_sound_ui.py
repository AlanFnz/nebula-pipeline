"""Compact authoring for the first visual-to-sound instrument."""
import copy

from PySide6.QtCore import Qt, Signal, QSignalBlocker
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QCheckBox, QComboBox, QDoubleSpinBox, QPushButton, QSlider, QProgressBar)

from synth_visual_sound import CONNECTIONS, default_sound, normalize_sound


class VisualSoundDialog(QDialog):
    configEdited = Signal(object)
    monitorVolumeChanged = Signal(float)
    monitorMutedChanged = Signal(bool)
    retryRequested = Signal()

    def __init__(self,parent=None):
        super().__init__(parent)
        self.setWindowTitle('Generate sound');self.resize(510,490)
        self.current=None;self.loaded=False
        layout=QVBoxLayout(self)
        label=QLabel('Pleated field · electric / tape')
        label.setProperty('sectionTitle',True);layout.addWidget(label)
        hint=QLabel('Sound follows the folds’ expansion, movement and reopening. Change the image to change the sound.')
        hint.setWordWrap(True);layout.addWidget(hint)
        self.enabled=QCheckBox('Enable generated sound');layout.addWidget(self.enabled)
        form=QFormLayout();form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.output=QComboBox();self.output.setAccessibleName('Audio output')
        for name,key in (('Generated sound','generated'),('Existing soundtrack / footage','existing'),('Silent','silent')):
            self.output.addItem(name,key)
        form.addRow('Audio output',self.output)
        self.gain=self.spin('Sound level',0,100,1,' %')
        self.pitch=self.spin('Base pitch',35,180,1,' Hz')
        self.smoothing=self.spin('Response smoothing',10,500,10,' ms')
        form.addRow('Sound level',self.gain);form.addRow('Base pitch',self.pitch)
        form.addRow('Response smoothing',self.smoothing);layout.addLayout(form)
        self.connections={};self.meters={}
        for key,title,_ in CONNECTIONS:
            row=QHBoxLayout();check=QCheckBox(title);row.addWidget(check,1)
            value=self.spin(title+' amount',0,200,5,' %');row.addWidget(value)
            layout.addLayout(row);self.connections[key]=(check,value)
            meter=QProgressBar();meter.setRange(0,100);meter.setTextVisible(False)
            meter.setValue(0);meter.setMaximumHeight(5);meter.setAccessibleName(title+' activity')
            layout.addWidget(meter);self.meters[key]=meter
        self.note=QLabel('Generated sound replaces other audio while selected. Monitor controls below do not change the export.')
        self.note.setWordWrap(True);layout.addWidget(self.note)
        row=QHBoxLayout();self.mute=QCheckBox('Mute monitor');row.addWidget(self.mute)
        row.addWidget(QLabel('Listen level'))
        self.volume=QSlider(Qt.Orientation.Horizontal);self.volume.setRange(0,100);self.volume.setValue(70)
        self.volume.setAccessibleName('Generated sound monitor level');row.addWidget(self.volume);layout.addLayout(row)
        self.volume.valueChanged.connect(lambda n:self.monitorVolumeChanged.emit(n/100))
        self.mute.toggled.connect(self.monitorMutedChanged)
        self.status=QLabel();self.status.setWordWrap(True);self.status.setTextFormat(Qt.TextFormat.PlainText);layout.addWidget(self.status)
        row=QHBoxLayout();self.retry=QPushButton('Prepare again');self.retry.clicked.connect(self.retryRequested)
        row.addWidget(self.retry);row.addStretch()
        self.apply_button=QPushButton('Apply && prepare');self.apply_button.setProperty('primary',True)
        self.apply_button.clicked.connect(self.apply);row.addWidget(self.apply_button)
        close=QPushButton('Close');close.clicked.connect(self.close);row.addWidget(close);layout.addLayout(row)

    @staticmethod
    def spin(name,low,high,step,suffix):
        control=QDoubleSpinBox();control.setRange(low,high);control.setDecimals(2)
        control.setSingleStep(step);control.setSuffix(suffix);control.setAccessibleName(name)
        control.setMinimumWidth(100)
        return control

    def set_config(self,config):
        if self.loaded and self.current==config: return
        self.loaded=True;self.current=copy.deepcopy(config)
        value=config or default_sound()
        self.enabled.setChecked(value['enabled'])
        self.output.setCurrentIndex(self.output.findData(value['output']))
        self.gain.setValue(value['gain']*100);self.pitch.setValue(value['pitch'])
        self.smoothing.setValue(value['smoothing']*1000)
        for key,(check,control) in self.connections.items():
            check.setChecked(value['connections'][key]['enabled'])
            control.setValue(value['connections'][key]['amount']*100)

    def apply(self):
        config=default_sound()
        config.update(enabled=self.enabled.isChecked(),output=self.output.currentData(),gain=self.gain.value()/100,
                      pitch=self.pitch.value(),smoothing=self.smoothing.value()/1000)
        config['connections']={key:dict(enabled=check.isChecked(),amount=control.value()/100)
                               for key,(check,control) in self.connections.items()}
        self.configEdited.emit(normalize_sound(config))

    def set_monitor(self,level,muted):
        with QSignalBlocker(self.volume): self.volume.setValue(round(level*100))
        with QSignalBlocker(self.mute): self.mute.setChecked(muted)

    def set_activity(self,expansion=0.,motion=0.,opening=0.):
        for key,value in zip(('body','friction','return'),(expansion,motion,opening)):
            self.meters[key].setValue(round(max(0,min(1,value))*100))
