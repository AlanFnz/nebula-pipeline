"""An editable 16-step pitch, rest, velocity and gate lane."""
import bisect
from PySide6.QtCore import Qt, Signal, QSignalBlocker
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QComboBox,
    QSpinBox,QDoubleSpinBox,QSlider,QCheckBox,QScrollArea,QFrame)
from synth_sound_sequence import (sequence_defaults, DIVISIONS, note_name, frequency_note, step_seconds)


class StepSequencer(QWidget):
    changed=Signal()
    gestureStarted=Signal()
    gestureFinished=Signal()

    def __init__(self):
        super().__init__(); self.loading=False; self.root=146.83; self.entries=[]; self.active=-1; self.schedule=[]; self.times=[]; self.period=.125
        layout=QVBoxLayout(self); layout.setContentsMargins(0,0,0,0)
        row=QHBoxLayout()
        self.bpm=QDoubleSpinBox(); self.bpm.setRange(30,240); self.bpm.setDecimals(1); self.bpm.setSuffix(' BPM'); self.bpm.setKeyboardTracking(False); self.bpm.setAccessibleName('Sequencer tempo');self.bpm.setToolTip('Tempo of the sound only. Does not change video speed.')
        self.division=QComboBox(); self.division.setAccessibleName('Step division')
        for key in DIVISIONS: self.division.addItem(key,key)
        self.length=QSpinBox(); self.length.setRange(1,16); self.length.setSuffix(' steps'); self.length.setAccessibleName('Sequence length'); self.length.setKeyboardTracking(False)
        self.trigger=QComboBox(); self.trigger.setAccessibleName('Sequencer trigger')
        self.trigger.addItem('Visual gestures','gesture'); self.trigger.addItem('Loop with timeline','loop')
        for label,widget in (('Tempo',self.bpm),('Division',self.division),('Length',self.length)):
            row.addWidget(QLabel(label)); row.addWidget(widget)
        layout.addLayout(row); row=QHBoxLayout(); row.addWidget(QLabel('Start'));row.addWidget(self.trigger,1); layout.addLayout(row)
        hint=QLabel('Turn a step off for a rest. Vel = strength · Gate = length. The image still shapes loudness and the filter.')
        hint.setWordWrap(True);layout.addWidget(hint)
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff);scroll.setFixedHeight(280)
        lane=QWidget();columns=QHBoxLayout(lane);columns.setContentsMargins(0,0,0,0);columns.setSpacing(4)
        for i in range(16):
            box=QFrame();box.setObjectName('sequenceStep');box.setMinimumWidth(68);col=QVBoxLayout(box);col.setContentsMargins(3,5,3,5);col.setSpacing(3)
            on=QCheckBox(str(i+1));on.setAccessibleName(f'Step {i+1} enabled');col.addWidget(on,0,Qt.AlignmentFlag.AlignHCenter)
            pitch=QSlider(Qt.Orientation.Vertical);pitch.setRange(-12,24);pitch.setAccessibleName(f'Step {i+1} pitch');pitch.setFixedHeight(84)
            pitch.sliderPressed.connect(self.gestureStarted);pitch.sliderReleased.connect(self.gestureFinished);col.addWidget(pitch,0,Qt.AlignmentFlag.AlignHCenter)
            name=QLabel();name.setAlignment(Qt.AlignmentFlag.AlignCenter);col.addWidget(name)
            offset=QSpinBox();offset.setRange(-12,24);offset.setSuffix(' st');offset.setAccessibleName(f'Step {i+1} semitones');offset.setKeyboardTracking(False);col.addWidget(offset)
            vel=QSpinBox();vel.setRange(0,100);vel.setPrefix('Vel ');vel.setAccessibleName(f'Step {i+1} velocity');vel.setKeyboardTracking(False);col.addWidget(vel)
            gate=QSpinBox();gate.setRange(10,100);gate.setPrefix('Gate ');gate.setAccessibleName(f'Step {i+1} gate');gate.setKeyboardTracking(False);col.addWidget(gate)
            for widget in (offset,vel,gate):
                widget.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons);widget.setAlignment(Qt.AlignmentFlag.AlignCenter);widget.setFixedWidth(64)
            pitch.valueChanged.connect(lambda value,n=i:self.pitch_changed(n,value,False))
            offset.valueChanged.connect(lambda value,n=i:self.pitch_changed(n,value,True))
            on.toggled.connect(self.emit_changed);vel.valueChanged.connect(self.emit_changed);gate.valueChanged.connect(self.emit_changed)
            self.entries.append((box,on,pitch,name,offset,vel,gate));columns.addWidget(box)
        columns.addStretch();scroll.setWidget(lane);layout.addWidget(scroll)
        for widget in (self.bpm,self.length):widget.valueChanged.connect(self.emit_changed)
        for widget in (self.division,self.trigger):widget.currentIndexChanged.connect(self.emit_changed)
        self.load(sequence_defaults())

    def pitch_changed(self,index,value,from_number):
        _,_,slider,_,number,_,_=self.entries[index]
        target=slider if from_number else number
        with QSignalBlocker(target):target.setValue(value)
        self.update_labels();self.emit_changed()

    def update_labels(self):
        for i,(box,on,pitch,name,offset,vel,gate) in enumerate(self.entries):
            box.setVisible(i<self.length.value());name.setText(note_name(frequency_note(self.root)+pitch.value()))
            name.setToolTip(f'{self.root*2**(pitch.value()/12):.2f} Hz · {pitch.value():+d} semitones from arpeggio root')

    def set_root(self,hz):self.root=hz;self.update_labels()
    def emit_changed(self,*_):
        if not self.loading:self.update_labels();self.changed.emit()

    def load(self,config):
        self.loading=True;self.bpm.setValue(config['bpm']);self.length.setValue(config['sequence_length'])
        self.division.setCurrentIndex(self.division.findData(config['subdivision']));self.trigger.setCurrentIndex(self.trigger.findData(config['sequence_trigger']))
        for entry,(_,on,pitch,_,offset,vel,gate) in zip(config['sequence'],self.entries):
            on.setChecked(entry['enabled']);pitch.setValue(entry['semitones']);offset.setValue(entry['semitones']);vel.setValue(round(entry['velocity']*100));gate.setValue(round(entry['gate']*100))
        self.loading=False;self.update_labels()

    def config(self):
        return dict(bpm=self.bpm.value(),subdivision=self.division.currentData(),sequence_length=self.length.value(),sequence_trigger=self.trigger.currentData(),
                    sequence=[dict(enabled=on.isChecked(),semitones=pitch.value(),velocity=vel.value()/100,gate=gate.value()/100)
                              for _,on,pitch,_,_,vel,gate in self.entries])

    def set_schedule(self,notes,config):
        self.schedule=notes;self.times=[n['time'] for n in notes];self.period=step_seconds(config)

    def set_time(self,seconds):
        index=bisect.bisect_right(self.times,seconds)-1
        step=self.schedule[index]['step'] if index>=0 and seconds<self.times[index]+self.period else -1
        if step==self.active:return
        for i in (self.active,step):
            if i>=0:self.entries[i][0].setStyleSheet('QFrame#sequenceStep {background:#354b3c;border:1px solid #acd88f;border-radius:4px;}' if i==step else '')
        self.active=step
