"""Compact authoring for the first visual-to-sound instrument."""
import copy

from PySide6.QtCore import Qt, Signal, QSignalBlocker
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QCheckBox, QComboBox, QDoubleSpinBox, QPushButton, QSlider, QProgressBar, QMessageBox)

from synth_visual_sound import acid_sound, default_sound, normalize_sound, sound_connections


class VisualSoundDialog(QDialog):
    configEdited = Signal(object)
    monitorVolumeChanged = Signal(float)
    monitorMutedChanged = Signal(bool)
    retryRequested = Signal()

    def __init__(self,parent=None):
        super().__init__(parent)
        self.setWindowTitle('Generate sound');self.resize(540,670)
        self.current=None;self.loaded=False
        layout=QVBoxLayout(self)
        label=QLabel('Pleated field · sound from motion')
        label.setProperty('sectionTitle',True);layout.addWidget(label)
        hint=QLabel('Sound follows the folds’ expansion, movement and reopening. Change the image to change the sound.')
        hint.setWordWrap(True);layout.addWidget(hint)
        self.enabled=QCheckBox('Enable generated sound');layout.addWidget(self.enabled)
        form=QFormLayout();form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.output=QComboBox();self.output.setAccessibleName('Audio output')
        for name,key in (('Generated sound','generated'),('Existing soundtrack / footage','existing'),('Silent','silent')):
            self.output.addItem(name,key)
        form.addRow('Audio output',self.output)
        self.voice=QComboBox();self.voice.setAccessibleName('Instrument')
        self.voice.addItem('Acid triangle + arpeggios',2);self.voice.addItem('Electric / tape (original)',1)
        form.addRow('Instrument',self.voice)
        self.gain=self.spin('Sound level',0,100,1,' %')
        self.pitch=self.spin('Base pitch',35,180,1,' Hz')
        self.smoothing=self.spin('Response smoothing',10,500,10,' ms')
        form.addRow('Sound level',self.gain);form.addRow('Base pitch',self.pitch)
        form.addRow('Response smoothing',self.smoothing)
        self.cutoff=self.spin('Filter closed',80,1800,20,' Hz')
        self.sweep=self.spin('Filter open',200,12000,100,' Hz')
        self.resonance=self.spin('Resonance',0,100,1,' %')
        self.arp_rate=self.spin('Arpeggio pace',50,200,5,' %')
        self.scale=QComboBox();self.scale.setAccessibleName('Arpeggio scale')
        for title,key in (('Minor pentatonic','pentatonic'),('Natural minor','minor'),('Dorian','dorian')): self.scale.addItem(title,key)
        self.acid_rows=[]
        for title,widget in (('Filter closed',self.cutoff),('Filter open',self.sweep),('Resonance',self.resonance),('Arpeggio pace',self.arp_rate),('Arpeggio scale',self.scale)):
            form.addRow(title,widget);self.acid_rows.append((form.labelForField(widget),widget))
        layout.addLayout(form)
        self.connection_layout=QVBoxLayout();layout.addLayout(self.connection_layout)
        self.connections={};self.meters={}
        self.voice.currentIndexChanged.connect(self.change_voice)
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
        self.load_values(config or acid_sound())

    def change_voice(self):
        value=acid_sound() if self.voice.currentData()==2 else default_sound()
        value.update(enabled=self.enabled.isChecked(),output=self.output.currentData(),gain=self.gain.value()/100)
        self.load_values(value)

    def load_values(self,value):
        with QSignalBlocker(self.voice): self.voice.setCurrentIndex(self.voice.findData(value['version']))
        acid=value['version']==2
        self.pitch.setRange(65 if acid else 35,440 if acid else 180)
        for label,widget in self.acid_rows: label.setVisible(acid);widget.setVisible(acid)
        self.enabled.setChecked(value['enabled'])
        self.output.setCurrentIndex(self.output.findData(value['output']))
        self.gain.setValue(value['gain']*100);self.pitch.setValue(value['pitch'])
        self.smoothing.setValue(value['smoothing']*1000)
        if acid:
            self.cutoff.setValue(value['cutoff']);self.sweep.setValue(value['sweep'])
            self.resonance.setValue(value['resonance']*100);self.arp_rate.setValue(value['arp_rate']*100)
            self.scale.setCurrentIndex(self.scale.findData(value['scale']))
        if set(self.connections)!=set(value['connections']):
            while self.connection_layout.count():
                item=self.connection_layout.takeAt(0)
                if item.widget(): item.widget().deleteLater()
                if item.layout():
                    row=item.layout()
                    while row.count(): row.takeAt(0).widget().deleteLater()
                    row.deleteLater()
            self.connections={};self.meters={}
            for key,title,_ in sound_connections(value):
                row=QHBoxLayout();check=QCheckBox(title);row.addWidget(check,1)
                control=self.spin(title+' amount',0,200,5,' %');row.addWidget(control)
                self.connection_layout.addLayout(row);self.connections[key]=(check,control)
                meter=QProgressBar();meter.setRange(0,100);meter.setTextVisible(False)
                meter.setValue(0);meter.setMaximumHeight(5);meter.setAccessibleName(title+' activity')
                self.connection_layout.addWidget(meter);self.meters[key]=meter
        for key,(check,control) in self.connections.items():
            check.setChecked(value['connections'][key]['enabled'])
            control.setValue(value['connections'][key]['amount']*100)

    def apply(self):
        config=acid_sound() if self.voice.currentData()==2 else default_sound()
        config.update(enabled=self.enabled.isChecked(),output=self.output.currentData(),gain=self.gain.value()/100,
                      pitch=self.pitch.value(),smoothing=self.smoothing.value()/1000)
        config['connections']={key:dict(enabled=check.isChecked(),amount=control.value()/100)
                               for key,(check,control) in self.connections.items()}
        if config['version']==2:
            config.update(cutoff=self.cutoff.value(),sweep=self.sweep.value(),resonance=self.resonance.value()/100,
                          arp_rate=self.arp_rate.value()/100,scale=self.scale.currentData())
        try: config=normalize_sound(config)
        except ValueError as exc:
            QMessageBox.warning(self,'Sound settings',str(exc));return
        self.configEdited.emit(config)

    def set_monitor(self,level,muted):
        with QSignalBlocker(self.volume): self.volume.setValue(round(level*100))
        with QSignalBlocker(self.mute): self.mute.setChecked(muted)

    def set_activity(self,expansion=0.,motion=0.,opening=0.,arpeggio=0.):
        for key,meter in self.meters.items():
            value=dict(body=expansion,friction=motion,filter=motion,return_=opening,arpeggio=arpeggio).get('return_' if key=='return' else key,0.)
            meter.setValue(round(max(0,min(1,value))*100))
