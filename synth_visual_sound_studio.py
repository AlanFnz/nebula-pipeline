"""Cancellable sound preparation, project undo and independent audio transport."""
import copy
import json
import tempfile
from collections import OrderedDict
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, QRunnable, Signal, QTimer
from PySide6.QtWidgets import QPushButton

from media import Cancellation
from synth_soundtrack import probe_soundtrack
from synth_soundtrack_preview import SoundtrackPreview
from synth_visual_sound import normalize_sound, audio_output, sound_key, write_sound, visual_signals, sound_for_sequence
from synth_visual_sound_ui import VisualSoundDialog
from synth_live_set import LIVE_SET
from synth_live_set_ui import LiveSetActions


class SoundSignals(QObject):
    done=Signal(object)
    failed=Signal(str)


class VisualSoundJob(QRunnable):
    def __init__(self,sequence,key,identity):
        super().__init__();self.sequence=copy.deepcopy(sequence);self.key=key;self.identity=identity
        self.cancel=Cancellation();self.signals=SoundSignals();self.folder=None

    def run(self):
        try:
            self.cancel.check();self.folder=tempfile.TemporaryDirectory(prefix='nebula-visual-sound-')
            signals=visual_signals(self.sequence,self.cancel)
            config=self.sequence['generated_sound']
            if config['version']==3:
                from synth_visual_sound_instrument import instrument_controls
                _,signals['arpeggio']=instrument_controls(signals,config)
            elif config['version']==4:
                from synth_lattice_sound import color_activity
                activity=color_activity(signals,config)
                signals.update(strum_activity=activity['strum'],step_activity=activity['steps'])
            elif config['version']==2:
                from synth_visual_sound_acid import arpeggio_activity
                signals['arpeggio']=arpeggio_activity(signals,config)
            path=write_sound(self.sequence,Path(self.folder.name)/'Generated sound.wav',self.cancel,signals=signals)
            track=probe_soundtrack(path,self.cancel);track['name']='Color waves / generated sound' if config['version']==4 else 'Pleated field / generated sound'
            self.cancel.check();self.signals.done.emit((track,signals))
        except Exception as exc:
            if self.folder: self.folder.cleanup()
            self.signals.failed.emit(str(exc) or 'Sound preparation cancelled')


class LiveSignalsJob(QRunnable):
    def __init__(self,sequence,key,identity,*,midi=False):
        super().__init__();self.sequence=copy.deepcopy(sequence);self.key=key;self.identity=identity
        self.cancel=Cancellation();self.signals=SoundSignals();self.midi=midi

    def run(self):
        try:
            signals=visual_signals(self.sequence,self.cancel)
            config=self.sequence.get('generated_sound',{})
            if config.get('version')==4 and not self.midi:
                from synth_lattice_sound import ColorWaveVoice
                # Prime the room on the preparation worker, before Listen.
                ColorWaveVoice(self.sequence,config,signals,cancel=self.cancel)
            self.cancel.check();self.signals.done.emit(signals)
        except Exception as exc: self.signals.failed.emit(str(exc))


class VisualSoundStudio(LiveSetActions):
    def init_visual_sound(self):
        self.midi_monitor_enabled=False
        self.visual_sound_dialog=None;self.visual_sound_job=None;self.visual_sound_key=None
        self.live_sound=None;self.live_signals_job=None;self.live_signals_key=None;self.live_signals=None;self.live_draft=None;self.live_meter_key=None
        self.live_document_cache=None
        self.live_base_signals=None;self.live_performance_config=None
        self.visual_sound_cache=OrderedDict();self.visual_sound_signals=None
        self.visual_sound_status='';self.visual_sound_volume=.7;self.visual_sound_muted=False
        self.visual_sound_player=SoundtrackPreview(self)
        self.visual_sound_player.set_monitor_volume(self.visual_sound_volume)
        self.visual_sound_player.statusChanged.connect(self.visual_sound_player_status)
        self.visual_sound_debounce=QTimer(self);self.visual_sound_debounce.setSingleShot(True)
        self.visual_sound_debounce.setInterval(180);self.visual_sound_debounce.timeout.connect(self.prepare_visual_sound)

    def build_visual_sound_action(self,layout):
        self.visual_sound_button=QPushButton('Generate sound…')
        self.visual_sound_button.setProperty('compact',True);self.visual_sound_button.setProperty('secondaryAction',True)
        self.visual_sound_button.setToolTip('Generate sound from Pleated field motion or Chromatic lattice color waves.')
        self.visual_sound_button.clicked.connect(self.open_visual_sound);layout.addWidget(self.visual_sound_button)

    def open_visual_sound(self,checked=False):
        if not self.composition or self.audition_pending(): return
        if self.visual_sound_dialog is None:
            dialog=VisualSoundDialog(self);self.visual_sound_dialog=dialog
            dialog.configEdited.connect(self.apply_visual_sound)
            dialog.historyChanged.connect(self.update_composition_history)
            dialog.finished.connect(self.update_composition_history)
            dialog.monitorVolumeChanged.connect(self.set_visual_sound_volume)
            dialog.monitorMutedChanged.connect(self.set_visual_sound_muted)
            dialog.retryRequested.connect(self.prepare_visual_sound)
            dialog.playRequested.connect(self.play.setChecked)
            dialog.previewRequested.connect(self.prepare_full_playback)
            dialog.draftChanged.connect(self.audition_visual_sound)
            dialog.liveChanged.connect(self.live_sound_changed)
            dialog.midiChanged.connect(self.change_midi_monitor)
            dialog.midiPanicRequested.connect(self.panic_midi)
            dialog.midiRefreshRequested.connect(self.refresh_midi_notes)
            dialog.live_set_button.linkRequested.connect(self.link_live_set)
            dialog.live_set_button.openRequested.connect(self.open_linked_live_set)
            dialog.live_set_button.unlinkRequested.connect(self.unlink_live_set)
            dialog.finished.connect(self.finish_live_sound)
            self.play.toggled.connect(dialog.set_playing)
        self.attach_sound_performance(self.visual_sound_dialog)
        self.visual_sound_dialog.set_config(self.sound_dialog_config())
        self.refresh_sound_context()
        self.visual_sound_dialog.set_monitor(self.visual_sound_volume,self.visual_sound_muted)
        self.visual_sound_dialog.set_playing(self.play.isChecked())
        self.visual_sound_dialog.status.setText(self.visual_sound_status or 'Apply sound to prepare this instrument.')
        self.visual_sound_dialog.show();self.visual_sound_dialog.raise_();self.visual_sound_dialog.activateWindow()
        self.update_composition_history()
        self.refresh_cache_status()
        self.visual_sound_dialog.set_video_frame(self.viewer.packet,self.current_time)
        self.audition_visual_sound(self.visual_sound_dialog.read_config())

    def wants_live_sound(self,config=None):
        dialog=self.visual_sound_dialog
        config=config or self.live_draft or (self.composition or {}).get('generated_sound') or {}
        listening = self.uses_midi(config) or (dialog.live.isChecked() if dialog and dialog.isVisible() else self.performing_visuals() or config.get('seamless_loop',False))
        return bool(listening and config.get('version') in (3,4) and config.get('output')=='generated')

    def uses_midi(self,config=None):
        config=config or self.live_draft or (self.composition or {}).get('generated_sound') or {}
        return self.midi_monitor_enabled and config.get('version') in (3,4) and config.get('output')=='generated'

    def change_midi_monitor(self,enabled):
        self.midi_monitor_enabled=enabled
        if self.live_sound: self.live_sound.close();self.live_sound=None
        if self.live_signals_job: self.live_signals_job.cancel.cancel();self.live_signals_job=None
        self.live_signals_key=None;self.live_base_signals=None
        self.audition_visual_sound(self.visual_sound_dialog.read_config())
        self.visual_sound_dialog.refresh_session()

    def panic_midi(self):
        self.play.setChecked(False)
        if self.uses_midi() and self.live_sound: self.live_sound.panic()

    def refresh_midi_notes(self):
        if self.uses_midi() and self.live_sound: self.live_sound.refresh_notes()

    def sound_dialog_config(self):
        return (self.composition or {}).get('generated_sound') or sound_for_sequence(self.preview_sequence())

    def refresh_sound_context(self):
        """Refresh on document edits/saves, never on the frame or audio clock."""
        dialog = self.visual_sound_dialog
        if dialog is None or not hasattr(self, 'clean_document'): return
        name = self.document_state()[1].get('name', 'Untitled')
        path = self.document_path
        dirty = self.has_unsaved_changes()
        navigation = self.workspace_navigation
        if navigation and navigation.montage and navigation.editor is self:
            montage = navigation.montage
            clip = next(c for c in montage.document['clips'] if c['id'] == navigation.clip_id)
            name = f"{montage.document['name']} › {clip['name']}"
            path = montage.path
            dirty = dirty or montage.document != montage.clean
        dialog.context_title.setText(name)
        dialog.context_title.setToolTip(name)
        dialog.file_state.setText('File: Not saved' if path is None else 'File: Unsaved changes' if dirty else 'File: Saved')
        dialog.file_state.setToolTip(str(path) if path else 'Save project to create a file.')
        dialog.live_set_button.set_link((self.composition or {}).get(LIVE_SET))
        dialog.applied_available = bool((self.composition or {}).get('generated_sound'))
        dialog.refresh_session()

    def resolve_sound_draft(self, purpose, *, leaving=False):
        dialog = self.visual_sound_dialog
        if dialog is None or not dialog.isVisible(): return True
        dialog.commit_pending_number()
        if not dialog.has_sound_draft(): return True
        choice = dialog.choose_pending_sound(purpose, leaving)
        if choice == 'cancel': return False
        if choice == 'apply':
            dialog.apply()
            return not dialog.has_sound_draft()
        if leaving:
            # Only sound is discarded. Visual edits remain in the document.
            dialog.draft_timer.stop();dialog.loaded=False
            dialog.set_config(self.sound_dialog_config())
            self.refresh_sound_context()
            self.audition_visual_sound(dialog.read_config())
        return True

    def live_sound_changed(self,*_):
        dialog=self.visual_sound_dialog
        if dialog:
            self.audition_visual_sound(dialog.read_config())

    def audition_visual_sound(self,config):
        config = config or (self.composition or {}).get('generated_sound') or {}
        self.live_draft=copy.deepcopy(config)
        if not self.wants_live_sound(config):
            self.finish_live_sound(refresh=True,keep_draft=True);return
        seq=self.performance_base_sequence()
        if not seq: return
        import hashlib,json
        from synth_preview import _visual_document
        from synth_visual_sound_live import LiveSoundMonitor
        from synth_live_midi import LiveMidiMonitor
        # Knobs only change the sound draft. Hash the visual document once per
        # revision, rather than deep-copying/serializing it on every drag event.
        revision=(self.document_identity,self.settings_generation,self.comparison_context())
        cached=self.live_document_cache
        if cached is None or cached[0]!=revision or cached[1] is not seq:
            key=(id(self.document_identity),hashlib.sha256(json.dumps(_visual_document(seq),sort_keys=True).encode()).hexdigest())
            self.live_document_cache=(revision,seq,key)
        else: key=cached[2]
        self.cancel_visual_sound();self.visual_sound_player.set_track(None)
        self.soundtrack_playback.set_monitor_muted(True)
        midi=self.uses_midi(config)
        if self.live_sound is not None and isinstance(self.live_sound,LiveMidiMonitor)!=midi:
            self.live_sound.close();self.live_sound=None;self.live_signals_key=None
        if self.live_sound is None:
            self.live_sound=LiveMidiMonitor(self) if midi else LiveSoundMonitor(self)
            self.live_sound.statusChanged.connect(self.set_visual_sound_status)
        self.live_sound.set_monitor(self.visual_sound_volume,self.visual_sound_muted)
        if key!=self.live_signals_key:
            if self.live_signals_job: self.live_signals_job.cancel.cancel()
            self.live_signals_key=key
            job=LiveSignalsJob(seq,key,self.document_identity,midi=midi);self.live_signals_job=job;self.pending_jobs.append(job)
            job.signals.done.connect(lambda result,j=job:self.live_signals_ready(j,result))
            job.signals.failed.connect(lambda error,j=job:self.live_signals_failed(j,error))
            self.set_visual_sound_status('Preparing visual motion for live sound…');self.jobs.start(job,-1)
        elif self.live_base_signals is not None and self.live_signals_job is None:
            self.refresh_performed_signals(config)
            self.live_sound.set_config(config)
            self.update_live_activity(config)
            self.set_visual_sound_status('MIDI → Nebula Visuals · Audio and mix in your DAW.' if midi else 'Live audition ready.')
            self.sync_soundtrack()

    def live_signals_ready(self,job,signals):
        if job in self.pending_jobs: self.pending_jobs.remove(job)
        if self.closing or job is not self.live_signals_job or job.identity is not self.document_identity or not self.wants_live_sound(): return
        self.live_signals_job=None;self.live_base_signals=signals
        self.live_performance_config=None
        self.refresh_performed_signals(self.live_draft, force=True)
        self.live_meter_key=None;self.update_live_activity(self.live_draft)
        self.set_visual_sound_status('MIDI → Nebula Visuals · Audio and mix in your DAW.' if self.uses_midi() else 'Live audition ready.')
        self.sync_soundtrack()

    def refresh_performed_signals(self, config, force=False):
        sequence = self.preview_sequence()
        performance = sequence.get('visual_performance')
        if not force and performance == self.live_performance_config: return
        from synth_performance import apply_signals
        signals = apply_signals(self.live_base_signals, performance, sequence['duration'], sequence['fps'])
        self.live_performance_config = copy.deepcopy(performance)
        self.live_signals = signals; self.visual_sound_signals = signals; self.live_meter_key = None
        if self.live_sound.sequence is None:
            self.live_sound.set_source(sequence, signals, config)
        else:
            self.live_sound.update_source(sequence, signals, config)

    def update_live_activity(self,config):
        if config['version']==4:
            key=json.dumps(config,sort_keys=True)
            if self.live_signals is not None and key!=self.live_meter_key:
                from synth_lattice_sound import color_activity
                activity=color_activity(self.live_signals,config)
                self.visual_sound_signals=dict(self.live_signals,strum_activity=activity['strum'],step_activity=activity['steps'])
                self.live_meter_key=key
            return
        key=(config['enabled'],config['arp_rate'],config['scale'],config['attack'],config['release'],
             config.get('seamless_loop',False),
             json.dumps({k:config.get(k) for k in ('arp_mode','bpm','subdivision','sequence_length','sequence_trigger','sequence')},sort_keys=True),
             config.get('arp_notes',4),config.get('arp_steps',0),config.get('arp_pattern','visual'),
             config['connections']['arpeggio']['enabled'],config['connections']['arpeggio']['amount'])
        if self.live_signals is not None and key!=self.live_meter_key:
            from synth_visual_sound_instrument import instrument_controls
            _,activity=instrument_controls(self.live_signals,config)
            self.visual_sound_signals=dict(self.live_signals,arpeggio=activity)
            self.live_meter_key=key
            if self.visual_sound_dialog:
                from synth_visual_sound_acid import gesture_notes
                notes=gesture_notes(self.live_signals,config,include_rests=True) if config.get('arp_mode')=='sequence' else []
                self.visual_sound_dialog.sequencer.set_schedule(notes,config)

    def live_signals_failed(self,job,error):
        if job in self.pending_jobs: self.pending_jobs.remove(job)
        if job is not self.live_signals_job or self.closing: return
        self.live_signals_job=None;self.live_signals_key=None
        self.set_visual_sound_status('Live sound: '+error)

    def finish_live_sound(self,*_,refresh=True,keep_draft=False):
        if self.live_signals_job: self.live_signals_job.cancel.cancel();self.live_signals_job=None
        self.live_signals_key=None;self.live_signals=None;self.live_base_signals=None;self.live_performance_config=None
        if self.live_sound: self.live_sound.stop()
        if not keep_draft:
            self.live_draft=None
            if self.visual_sound_dialog:
                self.visual_sound_dialog.draft_timer.stop()
                self.visual_sound_dialog.loaded=False
                self.visual_sound_dialog.set_config(self.sound_dialog_config())
        self.visual_sound_key=None
        if refresh and not self.closing: self.refresh_visual_sound()

    def apply_visual_sound(self,config):
        if not self.composition or not self.composer or self.audition_pending(): return
        config=normalize_sound(config)
        self.live_draft=copy.deepcopy(config)
        if config!=self.composition.get('generated_sound'):
            project=copy.deepcopy(self.composition);project['generated_sound']=config
            self.composer.commit(project,'generated-sound')
        elif self.wants_live_sound(config): self.audition_visual_sound(config)
        elif not self.visual_sound_job: self.prepare_visual_sound()
        self.refresh_sound_context()

    def set_visual_sound_volume(self,value):
        self.visual_sound_volume=value;self.visual_sound_player.set_monitor_volume(value)
        if self.live_sound: self.live_sound.set_monitor(value,self.visual_sound_muted)

    def set_visual_sound_muted(self,value):
        self.visual_sound_muted=value;self.visual_sound_player.set_monitor_muted(value)
        if self.live_sound: self.live_sound.set_monitor(self.visual_sound_volume,value)

    def visual_sound_player_status(self,message):
        if message: self.set_visual_sound_status(message)
        elif self.visual_sound_key in self.visual_sound_cache:
            self.set_visual_sound_status('Sound ready · press Play in the timeline.')

    def set_visual_sound_status(self,message):
        self.visual_sound_status=message
        if self.visual_sound_dialog: self.visual_sound_dialog.status.setText(message)

    def refresh_visual_sound(self):
        if not hasattr(self,'visual_sound_button'): return
        seq=self.preview_sequence();config=(seq or {}).get('generated_sound')
        supported=any(set(state.get('enabled',())) & {'pleated_field','chromatic_lattice'} for state in (seq or {}).get('states',{}).values())
        self.visual_sound_button.setEnabled(self.composition is not None and (supported or config is not None))
        if self.visual_sound_dialog:
            self.visual_sound_dialog.set_config(self.sound_dialog_config())
            if self.visual_sound_dialog.isVisible(): self.live_draft=self.visual_sound_dialog.read_config()
            self.refresh_sound_context()
        if self.wants_live_sound():
            self.visual_sound_button.setText('Generated sound…' if config else 'Generate sound…')
            self.audition_visual_sound(self.live_draft);return
        if self.live_sound: self.live_sound.stop()
        active=seq is not None and audio_output(seq)=='generated'
        # Authored imported audio remains intact. This output selector prevents
        # double monitoring; the previous monitor mute is restored on Existing.
        suppress=bool(config and config['output']!='existing')
        self.soundtrack_playback.set_monitor_muted(self.soundtrack_monitor_muted or suppress)
        key=sound_key(seq) if active else None
        if key!=self.visual_sound_key:
            self.cancel_visual_sound();self.visual_sound_key=key
            self.visual_sound_signals=None;self.visual_sound_player.set_track(None)
            if key is not None:
                if key in self.visual_sound_cache: self.use_cached_visual_sound(key)
                else:
                    self.set_visual_sound_status('Preparing sound from the image…')
                    self.visual_sound_debounce.start()
            else: self.set_visual_sound_status('Generated sound is off.' if config else '')
        if self.visual_sound_dialog:
            self.visual_sound_dialog.set_config(self.sound_dialog_config())
        self.visual_sound_button.setText('Generated sound…' if config else 'Generate sound…')

    def cancel_visual_sound(self):
        self.visual_sound_debounce.stop()
        job,self.visual_sound_job=self.visual_sound_job,None
        if job: job.cancel.cancel()

    def prepare_visual_sound(self):
        if self.closing: return
        if self.wants_live_sound():
            self.live_signals_key=None;self.audition_visual_sound(self.live_draft);return
        seq=self.preview_sequence()
        if not seq or audio_output(seq)!='generated': return
        key=sound_key(seq)
        if self.visual_sound_job and self.visual_sound_job.key==key: return
        self.cancel_visual_sound();self.visual_sound_key=key
        if key in self.visual_sound_cache:
            self.visual_sound_player.set_track(None)
            self.use_cached_visual_sound(key);return
        job=VisualSoundJob(seq,key,self.document_identity)
        self.visual_sound_job=job;self.pending_jobs.append(job)
        job.signals.done.connect(lambda result,j=job:self.visual_sound_ready(j,result))
        job.signals.failed.connect(lambda error,j=job:self.visual_sound_failed(j,error))
        self.set_visual_sound_status('Preparing sound from the image…');self.jobs.start(job,-1)

    def visual_sound_ready(self,job,result):
        if job in self.pending_jobs: self.pending_jobs.remove(job)
        if self.closing or self.visual_sound_job is not job or job.identity is not self.document_identity or job.key!=self.visual_sound_key:
            if self.visual_sound_job is job: self.visual_sound_job=None
            if job.folder: job.folder.cleanup()
            return
        self.visual_sound_job=None
        self.visual_sound_cache[job.key]=(job.folder,*result)
        self.use_cached_visual_sound(job.key)
        while len(self.visual_sound_cache)>3:
            _,(folder,_,_)=self.visual_sound_cache.popitem(last=False);folder.cleanup()

    def use_cached_visual_sound(self,key):
        _,track,self.visual_sound_signals=self.visual_sound_cache[key]
        self.visual_sound_cache.move_to_end(key)
        self.visual_sound_player.set_track(track)
        self.set_visual_sound_status('Sound ready · press Play in the timeline.')
        self.sync_soundtrack(force=True)

    def visual_sound_failed(self,job,error):
        if job in self.pending_jobs: self.pending_jobs.remove(job)
        if self.closing or self.visual_sound_job is not job: return
        self.visual_sound_job=None;self.set_visual_sound_status('Sound: '+error)

    def sync_visual_sound(self,seconds,playing,force=False):
        live=self.wants_live_sound() and self.live_sound is not None
        if live:
            if self.live_signals is not None: self.live_sound.sync(seconds,playing,force=force)
        else: self.visual_sound_player.sync(seconds,playing,force=force)
        dialog=self.visual_sound_dialog;signals=self.visual_sound_signals
        if dialog and dialog.isVisible():dialog.sequencer.set_time(seconds)
        if dialog and dialog.isVisible():
            if signals is None: dialog.set_activity()
            else:
                config=self.live_draft if live else (self.preview_sequence() or {}).get('generated_sound',{})
                if config.get('version')==4:
                    dialog.set_activity(expansion=float(np.interp(seconds,signals['time'],signals.get('strum_activity',np.zeros_like(signals['time'])))),
                                        arpeggio=float(np.interp(seconds,signals['time'],signals.get('step_activity',np.zeros_like(signals['time'])))))
                    return
                values=[]
                filter_key='filter' if config.get('version',1)>=2 else 'friction'
                for key,name in (('body','expansion'),(filter_key,'motion'),('return','opening'),('arpeggio','arpeggio')):
                    enabled=config.get('connections',{}).get(key,{}).get('enabled',False)
                    value=np.interp(seconds,signals['time'],signals[name])*np.interp(seconds,signals['time'],signals['presence']) if enabled and name in signals else 0.
                    values.append(value)
                dialog.set_activity(*values)

    def reset_visual_sound(self):
        if self.midi_monitor_enabled:
            self.midi_monitor_enabled=False
            if self.live_sound: self.live_sound.close();self.live_sound=None
            if self.visual_sound_dialog:
                from PySide6.QtCore import QSignalBlocker
                with QSignalBlocker(self.visual_sound_dialog.midi): self.visual_sound_dialog.midi.setChecked(False)
        self.finish_live_sound(refresh=False)
        self.cancel_visual_sound();self.visual_sound_key=None;self.visual_sound_signals=None
        self.visual_sound_player.set_track(None)
        if self.visual_sound_dialog: self.visual_sound_dialog.hide()

    def close_visual_sound(self):
        self.reset_visual_sound();self.visual_sound_player.close()
        if self.live_sound: self.live_sound.close();self.live_sound=None
        for folder,_,_ in self.visual_sound_cache.values(): folder.cleanup()
        self.visual_sound_cache.clear()
