"""Cancellable sound preparation, project undo and independent audio transport."""
import copy
import tempfile
from collections import OrderedDict
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, QRunnable, Signal, QTimer
from PySide6.QtWidgets import QPushButton

from media import Cancellation
from synth_soundtrack import probe_soundtrack
from synth_soundtrack_preview import SoundtrackPreview
from synth_visual_sound import normalize_sound, audio_output, sound_key, write_sound, visual_signals
from synth_visual_sound_ui import VisualSoundDialog


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
            if config['version']==2:
                from synth_visual_sound_acid import arpeggio_activity
                signals['arpeggio']=arpeggio_activity(signals,config)
            path=write_sound(self.sequence,Path(self.folder.name)/'Generated sound.wav',self.cancel,signals=signals)
            track=probe_soundtrack(path,self.cancel);track['name']='Pleated field / generated sound'
            self.cancel.check();self.signals.done.emit((track,signals))
        except Exception as exc:
            if self.folder: self.folder.cleanup()
            self.signals.failed.emit(str(exc) or 'Sound preparation cancelled')


class VisualSoundStudio:
    def init_visual_sound(self):
        self.visual_sound_dialog=None;self.visual_sound_job=None;self.visual_sound_key=None
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
        self.visual_sound_button.setToolTip('Synthesize sound from the motion of a Pleated field object.')
        self.visual_sound_button.clicked.connect(self.open_visual_sound);layout.addWidget(self.visual_sound_button)

    def open_visual_sound(self,checked=False):
        if not self.composition or self.audition_pending(): return
        if self.visual_sound_dialog is None:
            dialog=VisualSoundDialog(self);self.visual_sound_dialog=dialog
            dialog.configEdited.connect(self.apply_visual_sound)
            dialog.monitorVolumeChanged.connect(self.set_visual_sound_volume)
            dialog.monitorMutedChanged.connect(self.set_visual_sound_muted)
            dialog.retryRequested.connect(self.prepare_visual_sound)
        self.visual_sound_dialog.set_config(self.composition.get('generated_sound'))
        self.visual_sound_dialog.set_monitor(self.visual_sound_volume,self.visual_sound_muted)
        self.visual_sound_dialog.status.setText(self.visual_sound_status or 'Choose Apply & prepare to hear this instrument.')
        self.visual_sound_dialog.show();self.visual_sound_dialog.raise_();self.visual_sound_dialog.activateWindow()

    def apply_visual_sound(self,config):
        if not self.composition or not self.composer or self.audition_pending(): return
        config=normalize_sound(config)
        if config!=self.composition.get('generated_sound'):
            project=copy.deepcopy(self.composition);project['generated_sound']=config
            self.composer.commit(project,'generated-sound')
        elif not self.visual_sound_job: self.prepare_visual_sound()

    def set_visual_sound_volume(self,value):
        self.visual_sound_volume=value;self.visual_sound_player.set_monitor_volume(value)

    def set_visual_sound_muted(self,value):
        self.visual_sound_muted=value;self.visual_sound_player.set_monitor_muted(value)

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
        supported=any('pleated_field' in state.get('enabled',()) for state in (seq or {}).get('states',{}).values())
        self.visual_sound_button.setEnabled(self.composition is not None and (supported or config is not None))
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
            self.visual_sound_dialog.set_config((self.composition or {}).get('generated_sound'))
        self.visual_sound_button.setText('Generated sound…' if config else 'Generate sound…')

    def cancel_visual_sound(self):
        self.visual_sound_debounce.stop()
        job,self.visual_sound_job=self.visual_sound_job,None
        if job: job.cancel.cancel()

    def prepare_visual_sound(self):
        if self.closing: return
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
        self.visual_sound_player.sync(seconds,playing,force=force)
        dialog=self.visual_sound_dialog;signals=self.visual_sound_signals
        if dialog and dialog.isVisible():
            if signals is None: dialog.set_activity()
            else:
                config=(self.preview_sequence() or {}).get('generated_sound',{})
                values=[]
                filter_key='filter' if config.get('version')==2 else 'friction'
                for key,name in (('body','expansion'),(filter_key,'motion'),('return','opening'),('arpeggio','arpeggio')):
                    enabled=config.get('connections',{}).get(key,{}).get('enabled',False)
                    value=np.interp(seconds,signals['time'],signals[name])*np.interp(seconds,signals['time'],signals['presence']) if enabled and name in signals else 0.
                    values.append(value)
                dialog.set_activity(*values)

    def reset_visual_sound(self):
        self.cancel_visual_sound();self.visual_sound_key=None;self.visual_sound_signals=None
        self.visual_sound_player.set_track(None)
        if self.visual_sound_dialog: self.visual_sound_dialog.hide()

    def close_visual_sound(self):
        self.reset_visual_sound();self.visual_sound_player.close()
        for folder,_,_ in self.visual_sound_cache.values(): folder.cleanup()
        self.visual_sound_cache.clear()
