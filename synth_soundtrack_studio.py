"""Soundtrack authoring and lifecycle integration for the Studio window."""
from __future__ import annotations

import copy
import math
import time
from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal
from PySide6.QtWidgets import QFileDialog, QPushButton

from media import Cancellation
from synth_soundtrack import normalize_soundtrack, probe_soundtrack, waveform_peaks
from synth_soundtrack_preview import SoundtrackPreview
from synth_soundtrack_ui import SoundtrackDialog, SoundtrackLane


class SoundtrackSignals(QObject):
    done = Signal(object)
    failed = Signal(str)


class SoundtrackJob(QRunnable):
    def __init__(self, *, path=None, track=None):
        super().__init__()
        self.path, self.track = path, copy.deepcopy(track)
        self.cancel = Cancellation()
        self.signals = SoundtrackSignals()

    def run(self):
        try:
            result = probe_soundtrack(self.path, self.cancel) if self.path else waveform_peaks(self.track, self.cancel)
            self.cancel.check()
            self.signals.done.emit(result)
        except Exception as error:
            self.signals.failed.emit(str(error) or 'Soundtrack preparation cancelled')


class SoundtrackStudio:
    def init_soundtrack(self):
        self.soundtrack_dialog = None
        self.soundtrack_import_job = None
        self.soundtrack_wave_job = None
        self.soundtrack_wave_key = None
        self.soundtrack_wave_cache = OrderedDict()
        self.soundtrack_monitor_volume = 1.
        self.soundtrack_monitor_muted = False
        self.soundtrack_playback = SoundtrackPreview(self)
        self.soundtrack_playback.statusChanged.connect(self.soundtrack_status_changed)

    def build_soundtrack_lane(self, layout):
        self.soundtrack_lane = SoundtrackLane()
        self.soundtrack_lane.hide()
        self.soundtrack_lane.seekRequested.connect(self.seek_soundtrack)
        self.soundtrack_lane.editRequested.connect(self.open_soundtrack)
        layout.addWidget(self.soundtrack_lane)

    def build_soundtrack_action(self, layout):
        self.soundtrack_button = QPushButton('Soundtrack…')
        self.soundtrack_button.setProperty('compact', True)
        self.soundtrack_button.setProperty('secondaryAction', True)
        self.soundtrack_button.setToolTip('Import, trim and position an audio track for the whole project.')
        self.soundtrack_button.clicked.connect(self.open_soundtrack)
        layout.addWidget(self.soundtrack_button)

    def authored_soundtrack(self):
        return (self.composition or self.sequence or {}).get('soundtrack')

    def soundtrack_status_changed(self, status):
        if hasattr(self, 'soundtrack_lane'):
            self.soundtrack_lane.set_status(status)
        if self.soundtrack_dialog:
            self.soundtrack_dialog.set_status(status)

    def open_soundtrack(self, checked=False):
        if not self.composition:
            self.status.setText('Use this sequence in the composer to edit its soundtrack.')
            return
        if self.audition_pending():
            self.status.setText('Keep or discard the temporary variation before editing the soundtrack.')
            return
        if self.soundtrack_dialog is None:
            dialog = SoundtrackDialog(self)
            self.soundtrack_dialog = dialog
            dialog.trackEdited.connect(self.apply_soundtrack)
            dialog.importRequested.connect(self.import_soundtrack_dialog)
            dialog.relinkRequested.connect(lambda: self.import_soundtrack_dialog(relink=True))
            dialog.removeRequested.connect(lambda: self.apply_soundtrack(None))
            dialog.monitorVolumeChanged.connect(self.set_soundtrack_monitor_volume)
            dialog.monitorMutedChanged.connect(self.set_soundtrack_monitor_muted)
            dialog.finished.connect(lambda _result: self.cancel_soundtrack_import())
        self.soundtrack_dialog.set_track(self.authored_soundtrack(), self.sequence['duration'])
        self.soundtrack_dialog.set_monitor(self.soundtrack_monitor_volume, self.soundtrack_monitor_muted)
        self.soundtrack_dialog.set_busy(self.soundtrack_import_job is not None)
        self.soundtrack_dialog.set_status(self.soundtrack_playback.status)
        self.soundtrack_dialog.show()
        self.soundtrack_dialog.raise_()
        self.soundtrack_dialog.activateWindow()

    def set_soundtrack_monitor_volume(self, volume):
        self.soundtrack_monitor_volume = max(0., min(1., float(volume)))
        self.soundtrack_playback.set_monitor_volume(self.soundtrack_monitor_volume)

    def set_soundtrack_monitor_muted(self, muted):
        self.soundtrack_monitor_muted = bool(muted)
        self.soundtrack_playback.set_monitor_muted(self.soundtrack_monitor_muted)

    def import_soundtrack_dialog(self, checked=False, *, relink=False):
        track = self.authored_soundtrack()
        path, _ = QFileDialog.getOpenFileName(self.soundtrack_dialog or self,
            'Relink soundtrack' if relink else 'Import soundtrack',
            str(Path(track['path']).parent) if track else '',
            'Audio (*.wav *.mp3 *.m4a *.aac *.aif *.aiff *.flac *.ogg *.opus);;All files (*)')
        if path: self.start_soundtrack_import(path, relink=relink)

    def start_soundtrack_import(self, path, *, relink=False):
        if not self.composition or self.audition_pending(): return
        self.cancel_soundtrack_import()
        job = SoundtrackJob(path=str(path))
        job.document_identity = self.document_identity
        job.previous_track = copy.deepcopy(self.authored_soundtrack())
        job.relink = relink
        self.soundtrack_import_job = job
        self.pending_jobs.append(job)
        if self.soundtrack_dialog:
            self.soundtrack_dialog.set_busy(True)
            self.soundtrack_dialog.set_status('Reading audio… Close this window to cancel.')
        self.status.setText('Reading soundtrack…')
        job.signals.done.connect(lambda track, j=job: self.soundtrack_imported(j, track))
        job.signals.failed.connect(lambda error, j=job: self.soundtrack_import_failed(j, error))
        self.jobs.start(job)

    def cancel_soundtrack_import(self):
        job, self.soundtrack_import_job = self.soundtrack_import_job, None
        if job: job.cancel.cancel()
        if self.soundtrack_dialog: self.soundtrack_dialog.set_busy(False)

    def _release_soundtrack_job(self, job):
        if job in self.pending_jobs: self.pending_jobs.remove(job)

    def soundtrack_imported(self, job, track):
        self._release_soundtrack_job(job)
        if self.closing or self.soundtrack_import_job is not job: return
        self.soundtrack_import_job = None
        if self.soundtrack_dialog: self.soundtrack_dialog.set_busy(False)
        if job.document_identity is not self.document_identity or job.previous_track != self.authored_soundtrack(): return
        previous = job.previous_track
        if previous:
            track['id'] = previous['id']
            for key in ('offset', 'gain', 'end_mode', 'export_audio'):
                track[key] = previous[key]
            if job.relink:
                if track['duration'] + 1e-9 < previous['out']:
                    self.soundtrack_status_changed('Replacement audio is shorter than Out. Choose a longer file, or use Replace to reset the trim.')
                    return
                for key in ('in', 'out', 'name'): track[key] = previous[key]
        if job.relink:
            # Relinking the same file is also an explicit retry after a device
            # or decoder failure, even when no authored setting changes.
            self.soundtrack_playback.set_track(None)
        self.apply_soundtrack(track)
        self.refresh_soundtrack()
        self.status.setText('Soundtrack ready. Clip durations are unchanged.')

    def soundtrack_import_failed(self, job, error):
        self._release_soundtrack_job(job)
        if self.closing or self.soundtrack_import_job is not job: return
        self.soundtrack_import_job = None
        if self.soundtrack_dialog: self.soundtrack_dialog.set_busy(False)
        self.soundtrack_status_changed(error)
        self.status.setText(f'Soundtrack import: {error}')

    def apply_soundtrack(self, track):
        if not self.composition or not self.composer or self.audition_pending(): return
        try:
            track = normalize_soundtrack(track) if track is not None else None
            if track == self.authored_soundtrack(): return
            project = copy.deepcopy(self.composition)
            if track is None:
                project.pop('soundtrack', None)
                project.get('source', {}).pop('soundtrack', None)
            else:
                project['soundtrack'] = track
            self.composer.commit(project, 'soundtrack')
        except (ValueError, TypeError, KeyError) as error:
            self.soundtrack_status_changed(str(error))

    def refresh_soundtrack(self):
        if not hasattr(self, 'soundtrack_lane'): return
        track = (self.preview_sequence() or {}).get('soundtrack')
        duration = (self.sequence or {}).get('duration', self.preset['loop_seconds'])
        self.soundtrack_lane.set_track(track, duration)
        self.soundtrack_lane.setVisible(track is not None)
        self.soundtrack_button.setText('Soundtrack…' if track else '+ Soundtrack…')
        self.soundtrack_button.setEnabled(self.composition is not None)
        if hasattr(self, 'soundtrack_action'):
            self.soundtrack_action.setEnabled(self.composition is not None)
        self.soundtrack_playback.set_track(track)
        if self.soundtrack_dialog:
            self.soundtrack_dialog.set_track(self.authored_soundtrack(), duration)
            self.soundtrack_dialog.set_busy(self.soundtrack_import_job is not None)
            self.soundtrack_dialog.set_status(self.soundtrack_playback.status)
        key = None
        if track:
            identity = track.get('identity', {})
            key = (track['path'], identity.get('size'), identity.get('mtime_ns'), track['duration'])
        if key != self.soundtrack_wave_key:
            if self.soundtrack_wave_job: self.soundtrack_wave_job.cancel.cancel()
            self.soundtrack_wave_job = None
            self.soundtrack_wave_key = key
            self.soundtrack_lane.set_peaks([])
            if key in self.soundtrack_wave_cache:
                self.soundtrack_lane.set_peaks(self.soundtrack_wave_cache[key])
                self.soundtrack_wave_cache.move_to_end(key)
            elif track:
                self.soundtrack_lane.set_status(self.soundtrack_playback.status or 'Preparing waveform…')
                job = SoundtrackJob(track=track)
                job.wave_key = key
                self.soundtrack_wave_job = job
                self.pending_jobs.append(job)
                job.signals.done.connect(lambda peaks, j=job: self.soundtrack_wave_ready(j, peaks))
                job.signals.failed.connect(lambda error, j=job: self.soundtrack_wave_failed(j, error))
                self.jobs.start(job, -1)
        self.sync_soundtrack(force=True)

    def soundtrack_wave_ready(self, job, peaks):
        self._release_soundtrack_job(job)
        if self.closing or self.soundtrack_wave_job is not job: return
        self.soundtrack_wave_job = None
        self.soundtrack_wave_cache[job.wave_key] = peaks
        while len(self.soundtrack_wave_cache) > 4: self.soundtrack_wave_cache.popitem(last=False)
        self.soundtrack_lane.set_peaks(peaks)
        self.soundtrack_lane.set_status(self.soundtrack_playback.status)

    def soundtrack_wave_failed(self, job, error):
        self._release_soundtrack_job(job)
        if self.closing or self.soundtrack_wave_job is not job: return
        self.soundtrack_wave_job = None
        self.soundtrack_lane.set_status(error)

    def seek_soundtrack(self, seconds):
        value = max(0, min(self.timeline.maximum(), round(seconds * self.preview_fps())))
        if value == self.timeline.value(): self.scrub(value)
        else: self.timeline.setValue(value)

    def sync_soundtrack(self, *, force=False, seconds=None):
        if not hasattr(self, 'timeline') or self.closing: return
        if seconds is None:
            seconds = self.timeline.value() / self.preview_fps()
            if self.play.isChecked():
                elapsed = self.play_origin + (time.monotonic() - self.play_started) * self.preview_fps()
                whole = math.floor(elapsed)
                scope = self.active_preview_scope()
                seconds = (scope.frame_at(whole % max(1, scope.count)) + elapsed - whole) / self.preview_fps()
        self.soundtrack_lane.set_time(seconds)
        # Sampled effect auditions are separate from the project transport.
        playing = self.play.isChecked() and not self.discovery_session
        self.soundtrack_playback.sync(seconds, playing, force=force)

    def reset_soundtrack_work(self):
        self.cancel_soundtrack_import()
        if self.soundtrack_wave_job: self.soundtrack_wave_job.cancel.cancel()
        self.soundtrack_wave_job = None
        self.soundtrack_wave_key = None
        self.soundtrack_playback.set_track(None)
        if self.soundtrack_dialog: self.soundtrack_dialog.hide()

    def close_soundtrack(self):
        self.reset_soundtrack_work()
        self.soundtrack_playback.close()
