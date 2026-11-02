"""Rotary instrument controls and separate monitor/output settings."""
import copy
from PySide6.QtCore import Qt, Signal, QSignalBlocker, QTimer
from PySide6.QtWidgets import (QDialog,QWidget,QVBoxLayout,QHBoxLayout,QLabel,QCheckBox,
    QComboBox,QPushButton,QSlider,QProgressBar,QMessageBox,QTabWidget,QGroupBox,QScrollArea,QDoubleSpinBox,QSplitter)
from synth_visual_sound import acid_sound,instrument_sound,default_sound,normalize_sound,sound_connections
from synth_sound_knob import SoundKnob

FACTORIES={1:default_sound,2:acid_sound,3:instrument_sound}


class VisualSoundDialog(QDialog):
    configEdited=Signal(object)
    monitorVolumeChanged=Signal(float)
    monitorMutedChanged=Signal(bool)
    retryRequested=Signal()
    playRequested=Signal(bool)
    draftChanged=Signal(object)
    liveChanged=Signal(bool)
    previewRequested=Signal()

    def __init__(self,parent=None):
        super().__init__(parent);self.setWindowTitle('Generate sound');self.resize(1280,780)
        self.current=None;self.loaded=False;self.loading=False;layout=QVBoxLayout(self)
        label=QLabel('PLEATED / SYNTH');label.setProperty('sectionTitle',True);layout.addWidget(label)
        hint=QLabel('Live audition: play the video and turn the knobs to hear changes immediately. Apply saves your sound; closing without Apply restores the saved settings.')
        hint.setWordWrap(True);layout.addWidget(hint);row=QHBoxLayout()
        self.enabled=QCheckBox('Enable sound');row.addWidget(self.enabled)
        self.voice=QComboBox();self.voice.setAccessibleName('Instrument')
        for title,key in (('Layered resonant synth',3),('Acid triangle (original)',2),('Electric / tape (original)',1)): self.voice.addItem(title,key)
        row.addWidget(self.voice,1);self.output=QComboBox();self.output.setAccessibleName('Audio output')
        for title,key in (('Generated sound','generated'),('Existing soundtrack / footage','existing'),('Silent','silent')): self.output.addItem(title,key)
        row.addWidget(self.output);layout.addLayout(row)
        from synth_viewer import SynthViewer
        split=QSplitter(Qt.Orientation.Horizontal);left=QWidget();column=QVBoxLayout(left);column.setContentsMargins(0,0,8,0)
        self.video_preview=SynthViewer();self.video_preview.setAccessibleName('Live sound video preview');column.addWidget(self.video_preview,1)
        self.video_time=QLabel('00:00.00');column.addWidget(self.video_time)
        split.addWidget(left);self.tabs=QTabWidget();split.addWidget(self.tabs);split.setSizes([400,850]);layout.addWidget(split,1)
        sound=self.page('Sound');oscillators=self.page('Oscillators');motion=self.page('Motion && melody')
        self.gain=SoundKnob('Level',0,100,1,' %');self.pitch=SoundKnob('Root',35,440,1,' Hz',log=True)
        self.density=SoundKnob('Density',0,100,1,' %');self.drive=SoundKnob('Drive',0,100,1,' %');self.width=SoundKnob('Stereo',0,100,1,' %')
        self.density.setToolTip('Blend additional waveform harmonics into each oscillator. Zero keeps its fundamental.')
        self.knob_row(sound,'Tone',(self.pitch,self.density,self.drive,self.width,self.gain))
        self.opening=SoundKnob('Opening',0,100,1,' %');self.resonance=SoundKnob('Resonance',0,100,1,' %')
        self.cutoff=SoundKnob('Closed',80,1800,20,' Hz',log=True);self.sweep=SoundKnob('Open',200,12000,100,' Hz',log=True)
        self.smoothing=SoundKnob('Smoothing',10,500,10,' ms',log=True)
        self.knob_row(sound,'Filter',(self.opening,self.resonance,self.cutoff,self.sweep,self.smoothing));sound.addStretch()
        self.opening.setToolTip('Manual filter opening. Movement adds to this setting; disable its connection for a fixed opening.')
        self.unison=SoundKnob('Unison',1,5,1,' voices',integer=True);self.detune=SoundKnob('Detune',0,35,.5,' cents')
        self.detune.setToolTip('Pitch spread in cents between unison voices. Use two or more voices to hear it.')
        self.knob_row(oscillators,'Voice bank',(self.unison,self.detune));self.oscillators=[];osc_row=QHBoxLayout()
        for i in range(3):
            box=QGroupBox(f'OSC {i+1}');column=QVBoxLayout(box);top=QHBoxLayout()
            check=QCheckBox('On');check.setAccessibleName(f'Oscillator {i+1} enabled');top.addWidget(check)
            wave=QComboBox();wave.setAccessibleName(f'Oscillator {i+1} waveform')
            for key in ('triangle','sine','saw','square'): wave.addItem(key.capitalize(),key)
            top.addWidget(wave,1);column.addLayout(top)
            level=SoundKnob('Level',0,100,1,' %');tune=SoundKnob('Tune',-24,24,1,' st',integer=True);fine=SoundKnob('Fine (cents)',-50,50,.5)
            knobs=QHBoxLayout();knobs.setSpacing(0)
            for title,knob in (('Level',level),('Tune',tune),('Fine',fine)):
                knob.setMinimumWidth(80);knob.number.setFixedWidth(82)
                knob.number.setAccessibleName(f'Oscillator {i+1} {title}');knob.dial.setAccessibleName(f'Oscillator {i+1} {title} knob');knobs.addWidget(knob)
            column.addLayout(knobs);osc_row.addWidget(box);self.oscillators.append((check,wave,level,tune,fine))
        oscillators.addLayout(osc_row);oscillators.addStretch()
        self.continuity=SoundKnob('Continuity',0,100,1,' %')
        self.continuity.setToolTip('Keep small visible forms audible. At 0%, level follows their visible area directly. Higher values soften the drop during contraction. An absent object still fades to silence.')
        self.visual_dynamics=self.knob_row(motion,'Visual dynamics',(self.continuity,))
        self.attack=SoundKnob('Attack',12,150,1,' ms',log=True);self.release=SoundKnob('Release',60,600,10,' ms',log=True)
        self.arp_rate=SoundKnob('Pace',50,200,5,' %');self.knob_row(motion,'Short phrases',(self.attack,self.release,self.arp_rate))
        row=QHBoxLayout();row.addWidget(QLabel('Scale'));self.scale=QComboBox();self.scale.setAccessibleName('Arpeggio scale')
        for title,key in (('Minor pentatonic','pentatonic'),('Natural minor','minor'),('Dorian','dorian')): self.scale.addItem(title,key)
        row.addWidget(self.scale,1);motion.addLayout(row);self.connection_layout=QVBoxLayout();motion.addLayout(self.connection_layout)
        motion.addStretch();self.connections={};self.meters={};self.voice.currentIndexChanged.connect(self.change_voice)
        self.live=QCheckBox('Live audition');self.live.setChecked(True);self.live.setToolTip('Real-time listening for the layered resonant synth. Original instruments use Apply & prepare.')
        self.live.toggled.connect(self.liveChanged);layout.addWidget(self.live)
        video=QHBoxLayout();self.preview_button=QPushButton('Prepare all video frames');self.preview_button.clicked.connect(self.previewRequested)
        video.addWidget(self.preview_button);self.preview_status=QLabel();video.addWidget(self.preview_status,1);layout.addLayout(video)
        self.note=QLabel('Generated sound replaces other audio. Listen level and Mute affect monitoring only.');self.note.setWordWrap(True);layout.addWidget(self.note)
        row=QHBoxLayout();self.listen=QPushButton('Listen');self.listen.setCheckable(True);self.listen.toggled.connect(self.playRequested);row.addWidget(self.listen)
        self.mute=QCheckBox('Mute');row.addWidget(self.mute);row.addWidget(QLabel('Listen level'))
        self.volume=QSlider(Qt.Orientation.Horizontal);self.volume.setRange(0,100);self.volume.setValue(70)
        self.volume.setAccessibleName('Generated sound monitor level');row.addWidget(self.volume);layout.addLayout(row)
        self.volume.valueChanged.connect(lambda n:self.monitorVolumeChanged.emit(n/100));self.mute.toggled.connect(self.monitorMutedChanged)
        self.status=QLabel();self.status.setWordWrap(True);self.status.setTextFormat(Qt.TextFormat.PlainText);layout.addWidget(self.status)
        row=QHBoxLayout();self.retry=QPushButton('Prepare again');self.retry.clicked.connect(self.retryRequested);row.addWidget(self.retry);row.addStretch()
        self.apply_button=QPushButton('Apply && prepare');self.apply_button.setProperty('primary',True);self.apply_button.clicked.connect(self.apply);row.addWidget(self.apply_button)
        close=QPushButton('Close');close.clicked.connect(self.close);row.addWidget(close);layout.addLayout(row)
        self.draft_timer=QTimer(self);self.draft_timer.setSingleShot(True);self.draft_timer.setInterval(24)
        self.draft_timer.timeout.connect(self.emit_draft)
        for knob in self.findChildren(SoundKnob): knob.valueChanged.connect(self.queue_draft)
        for widget in (self.enabled,self.output,self.scale):
            (widget.toggled if isinstance(widget,QCheckBox) else widget.currentIndexChanged).connect(self.queue_draft)
        for check,wave,_,_,_ in self.oscillators:
            check.toggled.connect(self.queue_draft);wave.currentIndexChanged.connect(self.queue_draft)

    def queue_draft(self,*_):
        if not self.loading and self.loaded and not self.draft_timer.isActive(): self.draft_timer.start()

    def emit_draft(self):
        if not self.loaded or self.loading: return
        try: config=self.read_config()
        except ValueError as exc:
            self.status.setText(str(exc));return
        self.draftChanged.emit(config)

    def set_video_frame(self,packet,seconds):
        if packet is None: return
        self.video_preview.set_canvas_size(packet[0]);self.video_preview.set_packet(packet)
        self.video_time.setText(f'{int(seconds)//60:02d}:{seconds%60:05.2f}')

    def set_preview_status(self,message,preparing=False):
        self.preview_status.setText(message)
        self.preview_button.setText('Cancel full preview' if preparing else 'Prepare all video frames')

    def page(self,title):
        scroll=QScrollArea();scroll.setWidgetResizable(True);page=QWidget();layout=QVBoxLayout(page)
        scroll.setWidget(page);self.tabs.addTab(scroll,title);return layout

    @staticmethod
    def knob_row(layout,title,knobs):
        box=QGroupBox(title);row=QHBoxLayout(box)
        for knob in knobs: row.addWidget(knob)
        layout.addWidget(box)
        return box

    def set_config(self,config):
        if self.loaded and self.current==config: return
        self.loaded=True;self.current=copy.deepcopy(config);self.load_values(config or instrument_sound())

    def change_voice(self):
        value=FACTORIES[self.voice.currentData()]()
        value.update(enabled=self.enabled.isChecked(),output=self.output.currentData(),gain=self.gain.value()/100);self.load_values(value);self.queue_draft()

    def load_values(self,value):
        self.loading=True
        with QSignalBlocker(self.voice): self.voice.setCurrentIndex(self.voice.findData(value['version']))
        acid=value['version']>=2;layered=value['version']==3;self.pitch.setRange(65 if acid else 35,440 if acid else 180)
        self.visual_dynamics.setVisible(layered)
        self.tabs.setTabEnabled(1,layered)
        self.live.setEnabled(layered)
        self.apply_button.setText('Apply' if layered and self.live.isChecked() else 'Apply && prepare')
        if not layered and self.tabs.currentIndex()==1: self.tabs.setCurrentIndex(0)
        for control in (self.density,self.drive,self.width,self.opening,self.attack,self.release,self.continuity): control.setVisible(layered)
        for control in (self.resonance,self.cutoff,self.sweep,self.arp_rate,self.scale): control.setVisible(acid)
        self.enabled.setChecked(value['enabled']);self.output.setCurrentIndex(self.output.findData(value['output']))
        self.gain.setValue(value['gain']*100);self.pitch.setValue(value['pitch']);self.smoothing.setValue(value['smoothing']*1000)
        if acid:
            self.cutoff.setValue(value['cutoff']);self.sweep.setValue(value['sweep']);self.resonance.setValue(value['resonance']*100)
            self.arp_rate.setValue(value['arp_rate']*100);self.scale.setCurrentIndex(self.scale.findData(value['scale']))
        if layered:
            self.continuity.setValue(value.get('continuity',0.)*100)
            for key in ('opening','density','drive','width'): getattr(self,key).setValue(value[key]*100)
            for key in ('unison','detune'): getattr(self,key).setValue(value[key])
            self.attack.setValue(value['attack']*1000);self.release.setValue(value['release']*1000)
            for osc,(check,wave,level,tune,fine) in zip(value['oscillators'],self.oscillators):
                check.setChecked(osc['enabled']);wave.setCurrentIndex(wave.findData(osc['wave']));level.setValue(osc['level']*100)
                tune.setValue(osc['transpose']);fine.setValue(osc['detune'])
        if set(self.connections)!=set(value['connections']):
            while self.connection_layout.count(): self.connection_layout.takeAt(0).widget().deleteLater()
            self.connections={};self.meters={}
            for key,title,_ in sound_connections(value):
                box=QWidget();row=QHBoxLayout(box);row.setContentsMargins(0,0,0,0)
                check=QCheckBox(title);row.addWidget(check,1);meter=QProgressBar();meter.setRange(0,100)
                meter.setTextVisible(False);meter.setValue(0);meter.setMaximumHeight(5);meter.setAccessibleName(title+' activity');row.addWidget(meter,1)
                control=QDoubleSpinBox();control.setRange(0,200);control.setDecimals(2);control.setSingleStep(5)
                control.setSuffix(' %');control.setAccessibleName(title+' amount');control.setFixedWidth(115);row.addWidget(control)
                self.connection_layout.addWidget(box);self.connections[key]=(check,control);self.meters[key]=meter
                check.toggled.connect(self.queue_draft);control.valueChanged.connect(self.queue_draft)
        titles={key:title for key,title,_ in sound_connections(value)}
        for key,(check,control) in self.connections.items():
            check.setText(titles[key]);check.setChecked(value['connections'][key]['enabled']);control.setValue(value['connections'][key]['amount']*100)
        self.loading=False

    def read_config(self):
        config=FACTORIES[self.voice.currentData()]()
        config.update(enabled=self.enabled.isChecked(),output=self.output.currentData(),gain=self.gain.value()/100,pitch=self.pitch.value(),smoothing=self.smoothing.value()/1000)
        config['connections']={key:dict(enabled=check.isChecked(),amount=control.value()/100) for key,(check,control) in self.connections.items()}
        if config['version']>=2:
            config.update(cutoff=self.cutoff.value(),sweep=self.sweep.value(),resonance=self.resonance.value()/100,arp_rate=self.arp_rate.value()/100,scale=self.scale.currentData())
        if config['version']==3:
            for key in ('opening','density','drive','width'): config[key]=getattr(self,key).value()/100
            config.update(continuity=self.continuity.value()/100,unison=int(self.unison.value()),detune=self.detune.value(),attack=self.attack.value()/1000,release=self.release.value()/1000)
            config['oscillators']=[dict(id=f'osc{i+1}',enabled=check.isChecked(),wave=wave.currentData(),level=level.value()/100,transpose=int(tune.value()),detune=fine.value()) for i,(check,wave,level,tune,fine) in enumerate(self.oscillators)]
        return normalize_sound(config)

    def apply(self):
        try: config=self.read_config()
        except ValueError as exc: QMessageBox.warning(self,'Sound settings',str(exc));return
        self.draft_timer.stop()
        self.configEdited.emit(config)

    def set_monitor(self,level,muted):
        with QSignalBlocker(self.volume): self.volume.setValue(round(level*100))
        with QSignalBlocker(self.mute): self.mute.setChecked(muted)

    def set_playing(self,playing):
        with QSignalBlocker(self.listen): self.listen.setChecked(playing)
        self.listen.setText('Pause' if playing else 'Listen')

    def set_activity(self,expansion=0.,motion=0.,opening=0.,arpeggio=0.):
        values={'body':expansion,'friction':motion,'filter':motion,'return':opening,'arpeggio':arpeggio}
        for key,meter in self.meters.items(): meter.setValue(round(max(0,min(1,values[key]))*100))
