"""Rotary instrument controls and separate monitor/output settings."""
import copy
from PySide6.QtCore import Qt, Signal, QSignalBlocker, QTimer
from PySide6.QtWidgets import (QDialog,QWidget,QVBoxLayout,QHBoxLayout,QLabel,QCheckBox,
    QComboBox,QPushButton,QSlider,QProgressBar,QMessageBox,QTabWidget,QGroupBox,QScrollArea,QDoubleSpinBox,QSplitter)
from synth_visual_sound import acid_sound,instrument_sound,default_sound,normalize_sound,sound_connections
from synth_sound_knob import SoundKnob
from synth_sound_pitch import PitchControl
from synth_sound_sequencer_ui import StepSequencer
from synth_sound_history import SoundHistory
from synth_sound_session_ui import SoundSession
from synth_sound_sequence import sequence_defaults
from synth_sound_mixer import mixer_defaults
from synth_sound_mixer_ui import SoundMixer
from synth_lattice_sound import color_wave_sound
from synth_lattice_sound_ui import ColorWaveControls,PadSpaceControls,WaveSineControls
from synth_sound_chimes_ui import ChimeLayerControls
from synth_sound_choir_ui import ChoirControls

FACTORIES={1:default_sound,2:acid_sound,3:instrument_sound,4:color_wave_sound}


class VisualSoundDialog(SoundSession,SoundHistory,QDialog):
    historyChanged=Signal()
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
        self.init_session_header(layout);row=QHBoxLayout()
        self.enabled=QCheckBox('Enable sound');row.addWidget(self.enabled)
        self.voice=QComboBox();self.voice.setAccessibleName('Instrument')
        for title,key in (('Layered resonant synth',3),('Acid triangle (original)',2),('Electric / tape (original)',1)): self.voice.addItem(title,key)
        self.voice.addItem('Color waves / dual synth',4)
        row.addWidget(self.voice,1);self.output=QComboBox();self.output.setAccessibleName('Audio output')
        for title,key in (('Generated sound','generated'),('Existing soundtrack / footage','existing'),('Silent','silent')): self.output.addItem(title,key)
        row.addWidget(self.output);layout.addLayout(row)
        from synth_viewer import SynthViewer
        split=QSplitter(Qt.Orientation.Horizontal);left=QWidget();column=QVBoxLayout(left);column.setContentsMargins(0,0,8,0)
        self.sound_splitter=split;self.preview_pane=left;self.pattern_split_sizes=None
        self.video_preview=SynthViewer();self.video_preview.setAccessibleName('Live sound video preview');column.addWidget(self.video_preview,1)
        self.video_time=QLabel('00:00.00');column.addWidget(self.video_time)
        split.addWidget(left);self.tabs=QTabWidget();split.addWidget(self.tabs);split.setSizes([400,850]);layout.addWidget(split,1)
        sound=self.page('Sound');oscillators=self.page('Oscillators');arpeggio=self.page('Arpeggio');motion=self.page('Motion')
        mixer=self.page('Mixer');self.mixer=SoundMixer();mixer.addWidget(self.mixer)
        self.mixer.toggled.connect(self.queue_draft)
        self.gain=SoundKnob('Level',0,100,1,' %');self.pitch=PitchControl('Base pitch',35,440)
        self.pitch.setToolTip('Pitch of the sustained body. The layered synth has a separate arpeggio root in Arpeggio. Original instruments share this root.')
        self.density=SoundKnob('Density',0,100,1,' %');self.drive=SoundKnob('Drive',0,100,1,' %');self.width=SoundKnob('Stereo',0,100,1,' %')
        self.density.setToolTip('Blend additional waveform harmonics into each oscillator. Zero keeps its fundamental.')
        self.knob_row(sound,'Tone',(self.pitch,self.density,self.drive,self.width,self.gain))
        self.opening=SoundKnob('Opening',0,100,1,' %');self.resonance=SoundKnob('Resonance',0,100,1,' %')
        self.cutoff=SoundKnob('Closed',80,1800,20,' Hz',log=True);self.sweep=SoundKnob('Open',200,12000,100,' Hz',log=True)
        self.smoothing=SoundKnob('Smoothing',10,500,10,' ms',log=True)
        self.knob_row(sound,'Filter',(self.opening,self.resonance,self.cutoff,self.sweep,self.smoothing))
        self.seamless_loop=QCheckBox('Seamless audio loop');sound.addWidget(self.seamless_loop);sound.addStretch()
        self.seamless_loop.setToolTip('Carry note releases and filter motion across the timeline boundary, with no fade to silence. Sustained oscillators use whole cycles (a tiny tuning adjustment). Use a whole number of sequencer patterns for an even rhythm. This does not close the visual animation.')
        self.legacy_sound_widgets=[sound.itemAt(i).widget() for i in range(sound.count()) if sound.itemAt(i).widget()]
        self.color_wave=ColorWaveControls();sound.insertWidget(0,self.color_wave)
        pad=self.page('Pad && space');self.pad_space=PadSpaceControls();pad.addWidget(self.pad_space)
        chimes=self.page('Chimes');self.chime_layer=ChimeLayerControls();chimes.addWidget(self.chime_layer)
        self.chimes_tab=self.tabs.count()-1
        choir=self.page('Choir');self.choir=ChoirControls();choir.addWidget(self.choir)
        self.choir_tab=self.tabs.count()-1
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
        self.wave_sine=WaveSineControls();motion.addWidget(self.wave_sine)
        self.arp_pitch=PitchControl('Arpeggio root',65,440)
        self.arp_notes=SoundKnob('Notes',1,8,1,integer=True)
        self.arp_steps=SoundKnob('Steps',0,16,1,integer=True)
        self.arp_steps.number.setSpecialValueText('Auto (3–4)')
        self.arp_pitch.setToolTip('Tune the melody independently of the sustained body. Phrases play in the register above this root.')
        self.arp_notes.setToolTip('Number of distinct scale notes available in each phrase. Longer patterns reuse this palette; the visual gesture selects its starting degree.')
        self.arp_steps.setToolTip('Notes played per visual gesture, from 1 to 16. Auto keeps the original alternating 3–4-step phrases.')
        self.arp_sequence=self.knob_row(arpeggio,'Pitch and phrase',(self.arp_pitch,self.arp_notes,self.arp_steps))
        self.arp_mode=QComboBox();self.arp_mode.setAccessibleName('Arpeggio mode')
        self.arp_mode.addItem('Visual arpeggio · original','visual');self.arp_mode.addItem('Step sequencer','sequence');arpeggio.addWidget(self.arp_mode)
        self.sequencer=StepSequencer();arpeggio.addWidget(self.sequencer)
        self.sequencer.focusRequested.connect(self.refresh_pattern_focus)
        self.arp_mode.currentIndexChanged.connect(self.update_sequence_mode)
        self.sequencer.changed.connect(self.queue_draft)
        self.arp_pitch.valueChanged.connect(self.sequencer.set_root)
        self.arp_pattern=QComboBox();self.arp_pattern.setAccessibleName('Arpeggio pattern')
        for title,key in (('Visual motif','visual'),('Up','up'),('Down','down'),('Up & down','up_down')): self.arp_pattern.addItem(title,key)
        self.arp_pattern_box=QGroupBox('Pattern');row=QHBoxLayout(self.arp_pattern_box);row.addWidget(self.arp_pattern);arpeggio.addWidget(self.arp_pattern_box)
        self.arp_hint=QLabel('Visual gestures start each phrase. Notes sets the pitch palette; Steps sets the phrase length. Auto preserves the original 3–4 steps. Longer phrases finish before the next one starts.')
        self.arp_hint.setWordWrap(True);arpeggio.addWidget(self.arp_hint)
        self.attack=SoundKnob('Attack',12,150,1,' ms',log=True);self.release=SoundKnob('Release',60,600,10,' ms',log=True)
        self.articulation_toggle=QPushButton('Articulation ▸');self.articulation_toggle.setCheckable(True)
        self.articulation_toggle.setToolTip('Show attack and release. These shape each note independently of step Gate.')
        self.articulation_toggle.toggled.connect(self.update_sequence_mode);arpeggio.addWidget(self.articulation_toggle)
        self.arp_rate=SoundKnob('Pace',50,200,5,' %');self.articulation_box=self.knob_row(arpeggio,'Articulation and pace',(self.attack,self.release,self.arp_rate))
        self.arp_scale_row=QWidget();row=QHBoxLayout(self.arp_scale_row);row.setContentsMargins(0,0,0,0)
        row.addWidget(QLabel('Scale'));self.scale=QComboBox();self.scale.setAccessibleName('Arpeggio scale')
        for title,key in (('Minor pentatonic','pentatonic'),('Natural minor','minor'),('Dorian','dorian')): self.scale.addItem(title,key)
        row.addWidget(self.scale,1);arpeggio.addWidget(self.arp_scale_row);arpeggio.addStretch();self.connection_layout=QVBoxLayout();motion.addLayout(self.connection_layout)
        self.tabs.currentChanged.connect(self.refresh_pattern_focus)
        motion.addStretch();self.connections={};self.meters={};self.voice.currentIndexChanged.connect(self.change_voice)
        self.live=QCheckBox('Live audition');self.live.setChecked(True);self.live.setToolTip('Hear synth changes during playback. Turn off to hear applied sound. Original instruments prepare audio after Apply sound.')
        self.live.toggled.connect(self.liveChanged);layout.addWidget(self.live)
        video=QHBoxLayout();self.preview_button=QPushButton('Prepare all video frames');self.preview_button.clicked.connect(self.previewRequested)
        video.addWidget(self.preview_button);self.preview_status=QLabel();video.addWidget(self.preview_status,1);layout.addLayout(video)
        self.preview_source=QLabel();self.preview_source.setWordWrap(True);layout.addWidget(self.preview_source)
        row=QHBoxLayout();self.listen=QPushButton('Listen');self.listen.setCheckable(True);self.listen.toggled.connect(self.playRequested);row.addWidget(self.listen)
        self.mute=QCheckBox('Mute monitor');row.addWidget(self.mute);row.addWidget(QLabel('Listen level'))
        self.volume=QSlider(Qt.Orientation.Horizontal);self.volume.setRange(0,100);self.volume.setValue(70)
        self.volume.setAccessibleName('Generated sound monitor level');row.addWidget(self.volume);layout.addLayout(row)
        self.volume.setToolTip('Listening level only. Does not affect the saved sound or export. Use the mixer to change output levels.')
        self.mute.setToolTip('Mute listening only. Mixer Mute and Solo also affect exports.')
        self.volume.valueChanged.connect(lambda n:self.monitorVolumeChanged.emit(n/100));self.mute.toggled.connect(self.monitorMutedChanged)
        self.status=QLabel();self.status.setWordWrap(True);self.status.setTextFormat(Qt.TextFormat.PlainText);layout.addWidget(self.status)
        row=QHBoxLayout();self.retry=QPushButton('Prepare again');self.retry.clicked.connect(self.retryRequested);row.addWidget(self.retry);self.undo_button=QPushButton('Undo');self.redo_button=QPushButton('Redo')
        self.undo_button.clicked.connect(self.request_undo);self.redo_button.clicked.connect(self.request_redo)
        row.addWidget(self.undo_button);row.addWidget(self.redo_button);row.addStretch()
        self.apply_button=QPushButton('Apply && prepare');self.apply_button.setProperty('primary',True);self.apply_button.clicked.connect(self.apply);row.addWidget(self.apply_button)
        self.init_session_actions(row)
        close=QPushButton('Close');close.clicked.connect(self.close);row.addWidget(close);layout.addLayout(row)
        self.draft_timer=QTimer(self);self.draft_timer.setSingleShot(True);self.draft_timer.setInterval(24)
        self.draft_timer.timeout.connect(self.emit_draft)
        self.init_history()
        self.historyChanged.connect(self.refresh_session)
        self.live.toggled.connect(self.refresh_session);self.mute.toggled.connect(self.refresh_session)
        pitches=self.findChildren(PitchControl)
        for knob in self.findChildren(SoundKnob):
            if knob not in [p.knob for p in pitches]:knob.valueChanged.connect(self.queue_draft)
            knob.dial.sliderPressed.connect(self.begin_sound_gesture);knob.dial.sliderReleased.connect(self.end_sound_gesture)
        for pitch in pitches:pitch.valueChanged.connect(self.queue_draft)
        for combo in self.color_wave.combos:combo.currentIndexChanged.connect(self.queue_draft)
        self.color_wave.loop.toggled.connect(self.queue_draft)
        self.pad_space.enabled.toggled.connect(self.queue_draft);self.pad_space.follow.toggled.connect(self.queue_draft)
        self.pad_space.harmony.currentIndexChanged.connect(self.queue_draft)
        self.wave_sine.enabled.toggled.connect(self.queue_draft)
        self.chime_layer.enabled.toggled.connect(self.queue_draft);self.chime_layer.scale.currentIndexChanged.connect(self.queue_draft)
        self.chime_layer.tuning.currentIndexChanged.connect(self.queue_draft)
        self.choir.enabled.toggled.connect(self.queue_draft)
        self.sequencer.gestureStarted.connect(self.begin_sound_gesture);self.sequencer.gestureFinished.connect(self.end_sound_gesture)
        for widget in (self.enabled,self.output,self.scale,self.arp_pattern,self.arp_mode,self.seamless_loop):
            (widget.toggled if isinstance(widget,QCheckBox) else widget.currentIndexChanged).connect(self.queue_draft)
        for check,wave,_,_,_ in self.oscillators:
            check.toggled.connect(self.queue_draft);wave.currentIndexChanged.connect(self.queue_draft)

    def queue_draft(self,*_):
        if self.loading or not self.loaded:return
        self.record_sound_edit()
        if not self.draft_timer.isActive(): self.draft_timer.start()

    def update_sequence_mode(self):
        layered=self.voice.currentData()==3
        custom=layered and self.arp_mode.currentData()=='sequence'
        self.sequencer.setVisible(custom);self.arp_mode.setVisible(layered);self.arp_pitch.set_compact(custom)
        for widget in (self.arp_notes,self.arp_steps,self.arp_pattern_box,self.arp_hint):widget.setVisible(layered and not custom)
        self.arp_rate.setVisible(self.voice.currentData()>=2 and not custom);self.scale.setEnabled(not custom)
        self.arp_scale_row.setVisible(not custom)
        self.articulation_toggle.setVisible(custom)
        self.articulation_toggle.setText('Articulation ▾' if self.articulation_toggle.isChecked() else 'Articulation ▸')
        self.articulation_box.setVisible(not custom or self.articulation_toggle.isChecked())
        self.refresh_pattern_focus()

    def refresh_pattern_focus(self,*_):
        focus=(self.tabs.currentIndex()==2 and self.voice.currentData()==3
               and self.arp_mode.currentData()=='sequence' and self.sequencer.focus_button.isChecked())
        if focus and self.pattern_split_sizes is None:
            self.pattern_split_sizes=self.sound_splitter.sizes();self.preview_pane.hide()
        elif not focus and self.pattern_split_sizes is not None:
            self.preview_pane.show();self.sound_splitter.setSizes(self.pattern_split_sizes);self.pattern_split_sizes=None

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
        self.applied_values=copy.deepcopy(self.read_config());self.reset_history()

    def change_voice(self):
        value=FACTORIES[self.voice.currentData()]()
        value.update(enabled=self.enabled.isChecked(),output=self.output.currentData(),gain=self.gain.value()/100);self.load_values(value);self.queue_draft()

    def load_values(self,value):
        self.loading=True
        with QSignalBlocker(self.voice): self.voice.setCurrentIndex(self.voice.findData(value['version']))
        color=value['version']==4
        self.color_wave.setVisible(color);self.wave_sine.setVisible(color)
        self.tabs.setTabVisible(5,color)
        self.tabs.setTabVisible(self.chimes_tab,color)
        self.tabs.setTabVisible(self.choir_tab,color)
        for widget in self.legacy_sound_widgets:widget.setVisible(not color)
        self.mixer.set_color_wave(color)
        for i in range(self.voice.count()):self.voice.model().item(i).setEnabled((self.voice.itemData(i)==4)==color)
        if color:
            self.color_wave.load(value);self.pad_space.load(value);self.wave_sine.load(value);self.chime_layer.load(value);self.choir.load(value);self.mixer.load(value['mixer'])
            self.visual_dynamics.hide()
            for i in (1,2):self.tabs.setTabVisible(i,False)
            self.live.setEnabled(True)
            self.enabled.setChecked(value['enabled']);self.output.setCurrentIndex(self.output.findData(value['output']))
            self.load_connections(value);self.loading=False;return
        for i in (1,2):self.tabs.setTabVisible(i,True)
        acid=value['version']>=2;layered=value['version']==3;self.pitch.setRange(65 if acid else 35,440 if acid else 180)
        self.visual_dynamics.setVisible(layered)
        self.seamless_loop.setVisible(layered)
        self.seamless_loop.setChecked(value.get('seamless_loop',False))
        if (not layered and self.tabs.currentIndex() in (1,4)) or (not acid and self.tabs.currentIndex()==2): self.tabs.setCurrentIndex(0)
        self.tabs.setTabEnabled(1,layered)
        self.tabs.setTabEnabled(4,layered)
        self.tabs.setTabEnabled(2,acid)
        for widget in (self.arp_sequence,self.arp_pattern_box,self.arp_hint): widget.setVisible(layered)
        self.live.setEnabled(layered)
        for control in (self.density,self.drive,self.width,self.opening,self.attack,self.release,self.continuity): control.setVisible(layered)
        for control in (self.resonance,self.cutoff,self.sweep,self.arp_rate,self.scale): control.setVisible(acid)
        self.enabled.setChecked(value['enabled']);self.output.setCurrentIndex(self.output.findData(value['output']))
        self.gain.setValue(value['gain']*100);self.pitch.load(value['pitch'],value.get('pitch_mode','hz'));self.smoothing.setValue(value['smoothing']*1000)
        if acid:
            self.cutoff.setValue(value['cutoff']);self.sweep.setValue(value['sweep']);self.resonance.setValue(value['resonance']*100)
            self.arp_rate.setValue(value['arp_rate']*100);self.scale.setCurrentIndex(self.scale.findData(value['scale']))
        if layered:
            self.mixer.load(value.get('mixer', mixer_defaults()))
            self.arp_pitch.load(value.get('arp_pitch',value['pitch']),value.get('arp_pitch_mode','hz'))
            self.arp_mode.setCurrentIndex(self.arp_mode.findData(value.get('arp_mode','visual')))
            self.sequencer.load(dict(sequence_defaults(),**{k:v for k,v in value.items() if k in sequence_defaults()}))
            self.sequencer.set_root(self.arp_pitch.value())
            self.arp_notes.setValue(value.get('arp_notes',4));self.arp_steps.setValue(value.get('arp_steps',0))
            self.arp_pattern.setCurrentIndex(self.arp_pattern.findData(value.get('arp_pattern','visual')))
            self.continuity.setValue(value.get('continuity',0.)*100)
            for key in ('opening','density','drive','width'): getattr(self,key).setValue(value[key]*100)
            for key in ('unison','detune'): getattr(self,key).setValue(value[key])
            self.attack.setValue(value['attack']*1000);self.release.setValue(value['release']*1000)
            for osc,(check,wave,level,tune,fine) in zip(value['oscillators'],self.oscillators):
                check.setChecked(osc['enabled']);wave.setCurrentIndex(wave.findData(osc['wave']));level.setValue(osc['level']*100)
                tune.setValue(osc['transpose']);fine.setValue(osc['detune'])
        self.load_connections(value)
        self.update_sequence_mode();self.loading=False

    def load_connections(self,value):
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

    def read_config(self):
        if self.voice.currentData()==4:
            config=self.color_wave.config()
            config.update(self.pad_space.config());config['wave']=self.wave_sine.config()
            config['chime_layer']=self.chime_layer.config()
            config['choir']=self.choir.config()
            config.update(enabled=self.enabled.isChecked(),output=self.output.currentData(),mixer=self.mixer.config())
            config['connections']={key:dict(enabled=check.isChecked(),amount=control.value()/100) for key,(check,control) in self.connections.items()}
            return normalize_sound(config)
        config=FACTORIES[self.voice.currentData()]()
        config.update(enabled=self.enabled.isChecked(),output=self.output.currentData(),gain=self.gain.value()/100,pitch=self.pitch.value(),pitch_mode=self.pitch.tuning(),smoothing=self.smoothing.value()/1000)
        config['connections']={key:dict(enabled=check.isChecked(),amount=control.value()/100) for key,(check,control) in self.connections.items()}
        if config['version']>=2:
            config.update(cutoff=self.cutoff.value(),sweep=self.sweep.value(),resonance=self.resonance.value()/100,arp_rate=self.arp_rate.value()/100,scale=self.scale.currentData())
        if config['version']==3:
            config['seamless_loop']=self.seamless_loop.isChecked()
            config['mixer']=self.mixer.config()
            config.update(arp_mode=self.arp_mode.currentData(),arp_pitch_mode=self.arp_pitch.tuning(),**self.sequencer.config())
            config.update(arp_pitch=self.arp_pitch.value(),arp_notes=int(self.arp_notes.value()),
                          arp_steps=int(self.arp_steps.value()),arp_pattern=self.arp_pattern.currentData())
            for key in ('opening','density','drive','width'): config[key]=getattr(self,key).value()/100
            config.update(continuity=self.continuity.value()/100,unison=int(self.unison.value()),detune=self.detune.value(),attack=self.attack.value()/1000,release=self.release.value()/1000)
            config['oscillators']=[dict(id=f'osc{i+1}',enabled=check.isChecked(),wave=wave.currentData(),level=level.value()/100,transpose=int(tune.value()),detune=fine.value()) for i,(check,wave,level,tune,fine) in enumerate(self.oscillators)]
        return normalize_sound(config)

    def apply(self):
        self.commit_pending_number()
        try: config=self.read_config()
        except ValueError as exc: QMessageBox.warning(self,'Sound settings',str(exc));return
        self.draft_timer.stop()
        self.configEdited.emit(config)
        self.reset_history()

    def set_monitor(self,level,muted):
        with QSignalBlocker(self.volume): self.volume.setValue(round(level*100))
        with QSignalBlocker(self.mute): self.mute.setChecked(muted)
        self.refresh_session()

    def set_playing(self,playing):
        with QSignalBlocker(self.listen): self.listen.setChecked(playing)
        self.listen.setText('Pause' if playing else 'Listen')
        self.refresh_session()

    def set_activity(self,expansion=0.,motion=0.,opening=0.,arpeggio=0.):
        values={'body':expansion,'friction':motion,'filter':motion,'return':opening,'arpeggio':arpeggio,'strum':expansion,'steps':arpeggio}
        for key,meter in self.meters.items(): meter.setValue(round(max(0,min(1,values[key]))*100))
