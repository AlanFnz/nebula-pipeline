"""Studio authoring and cancellable preparation of soundtrack responses."""
from __future__ import annotations

import copy

from PySide6.QtCore import QObject, QRunnable, Signal

from media import Cancellation
from synth_audio_reactivity import normalize_reactivity, prepare_reactivity, cached_responses
from synth_audio_reactivity_ui import AudioReactivityDialog
from synth_preview import audio_reactivity_inputs, _file_fingerprint


class AudioReactivitySignals(QObject):
    done = Signal(object)
    failed = Signal(str)


class AudioReactivityJob(QRunnable):
    def __init__(self, sequence, document_identity, key):
        super().__init__()
        self.sequence = copy.deepcopy(sequence)
        self.document_identity, self.key = document_identity, key
        self.cancel = Cancellation()
        self.signals = AudioReactivitySignals()

    def run(self):
        try:
            self.cancel.check()
            analysis = prepare_reactivity(self.sequence, cancel=self.cancel)
            self.cancel.check()
            self.signals.done.emit(analysis)
        except Exception as error:
            self.signals.failed.emit(str(error) or 'Audio analysis cancelled')


def _analysis_key(sequence):
    inputs = audio_reactivity_inputs(sequence)
    if inputs is None:
        return None
    # Called on document/source refresh, never by the response meter.
    return (inputs, _file_fingerprint(inputs['track']['path']))


class AudioReactivityStudio:
    def init_audio_reactivity(self):
        self.audio_reactivity_dialog = None
        self.audio_reactivity_job = None
        self.audio_reactivity_key = None
        self.audio_reactivity_status = ''
        self.audio_reactivity_available = False

    def open_audio_reactivity(self, checked=False):
        if not self.composition or not self.composer:
            self.status.setText('Use this sequence in the composer to edit audio responses.')
            return
        if self.audition_pending():
            self.status.setText('Keep or discard the temporary variation before editing audio responses.')
            return
        if self.audio_reactivity_dialog is None:
            dialog = AudioReactivityDialog(self)
            self.audio_reactivity_dialog = dialog
            dialog.configEdited.connect(self.apply_audio_reactivity)
            dialog.prepareRequested.connect(self.prepare_audio_reactivity)
            dialog.finished.connect(lambda _result: self.cancel_audio_reactivity())
        self.audio_reactivity_dialog.set_project(self.composition)
        self.refresh_audio_reactivity()
        sequence = self.preview_sequence()
        if _analysis_key(sequence) is not None:
            responses = cached_responses(sequence, self.timeline.value() / self.preview_fps())
            if not self.audio_reactivity_available or responses is None:
                self.prepare_audio_reactivity()
            elif self.audio_reactivity_job is None:
                self.audio_reactivity_available = True
                self.set_audio_reactivity_status('Audio responses ready.')
        self.audio_reactivity_dialog.set_busy(self.audio_reactivity_job is not None)
        self.audio_reactivity_dialog.set_status(self.audio_reactivity_status)
        self.audio_reactivity_dialog.show()
        self.sync_audio_reactivity(self.timeline.value() / self.preview_fps())
        self.audio_reactivity_dialog.raise_()
        self.audio_reactivity_dialog.activateWindow()

    def apply_audio_reactivity(self, config):
        if not self.composition or not self.composer or self.audition_pending():
            return
        try:
            config = normalize_reactivity(config, self.authored_soundtrack()) if config is not None else None
            # Removing the last connection restores the pre-reactivity document
            # format instead of retaining an empty schema-5 feature marker.
            if config is not None and not config['mappings']:
                config = None
            if config == self.composition.get('audio_reactivity'):
                return
            project = copy.deepcopy(self.composition)
            if config is None:
                project.pop('audio_reactivity', None)
                project.get('source', {}).pop('audio_reactivity', None)
            else:
                project['audio_reactivity'] = config
            self.composer.commit(project, 'audio-reactivity')
        except (ValueError, TypeError, KeyError) as error:
            self.set_audio_reactivity_status(str(error))

    def set_audio_reactivity_status(self, status):
        self.audio_reactivity_status = str(status)
        if self.audio_reactivity_dialog:
            self.audio_reactivity_dialog.set_status(self.audio_reactivity_status)

    def refresh_audio_reactivity(self):
        sequence = self.preview_sequence()
        key = _analysis_key(sequence)
        if key != self.audio_reactivity_key:
            self.cancel_audio_reactivity()
            self.audio_reactivity_key = key
            self.audio_reactivity_available = False
            self.set_audio_reactivity_status('' if key is None else 'Preparing audio responses…')
            if key is not None and not self.closing:
                self.prepare_audio_reactivity()
        if self.audio_reactivity_dialog:
            self.audio_reactivity_dialog.set_project(self.composition or {})
            self.audio_reactivity_dialog.set_busy(self.audio_reactivity_job is not None)
            self.audio_reactivity_dialog.set_status(self.audio_reactivity_status)
            self.sync_audio_reactivity(self.timeline.value() / self.preview_fps())

    def prepare_audio_reactivity(self):
        if self.closing:
            return
        sequence = self.preview_sequence()
        key = _analysis_key(sequence)
        if key is None:
            self.set_audio_reactivity_status('Apply an enabled audio response before analyzing audio.')
            return
        if self.audio_reactivity_job is not None and self.audio_reactivity_job.key == key:
            return
        self.cancel_audio_reactivity()
        self.audio_reactivity_key = key
        self.audio_reactivity_available = False
        job = AudioReactivityJob(sequence, self.document_identity, copy.deepcopy(key))
        self.audio_reactivity_job = job
        self.pending_jobs.append(job)
        self.set_audio_reactivity_status('Preparing audio responses…')
        if self.audio_reactivity_dialog:
            self.audio_reactivity_dialog.set_busy(True)
            self.audio_reactivity_dialog.set_responses(None)
        job.signals.done.connect(lambda result, j=job: self.audio_reactivity_prepared(j, result=result))
        job.signals.failed.connect(lambda error, j=job: self.audio_reactivity_prepared(j, error=error))
        self.jobs.start(job, -1)

    def cancel_audio_reactivity(self):
        job, self.audio_reactivity_job = self.audio_reactivity_job, None
        if job is not None:
            job.cancel.cancel()
            self.set_audio_reactivity_status('Audio analysis cancelled. Analyze audio to prepare responses.')
        if self.audio_reactivity_dialog:
            self.audio_reactivity_dialog.set_busy(False)

    def audio_reactivity_prepared(self, job, *, result=None, error=None):
        if job in self.pending_jobs:
            self.pending_jobs.remove(job)
        if (self.closing or self.audio_reactivity_job is not job or job.cancel.event.is_set()
                or job.document_identity is not self.document_identity):
            return
        self.audio_reactivity_job = None
        if self.audio_reactivity_dialog:
            self.audio_reactivity_dialog.set_busy(False)
        if job.key != _analysis_key(self.preview_sequence()):
            self.refresh_audio_reactivity()
            return
        self.set_audio_reactivity_status('Audio responses ready.' if error is None else 'Audio analysis unavailable: ' + error)
        self.audio_reactivity_available = error is None
        self.sync_audio_reactivity(self.timeline.value() / self.preview_fps())
        if error is None:
            self.request_frame()

    def sync_audio_reactivity(self, seconds):
        dialog = self.audio_reactivity_dialog
        if dialog is None or not dialog.isVisible() or self.closing:
            return
        sequence = self.preview_sequence()
        if not sequence:
            dialog.set_responses(None)
            dialog.set_active_paths(())
            return
        # This accessor never reads a media file or starts an analysis worker.
        try:
            responses = None if self.audio_reactivity_key is not None and not self.audio_reactivity_available else cached_responses(sequence, seconds)
            dialog.set_responses(responses)
            from synth_sequence import resolve_sequence_frame
            base = resolve_sequence_frame(sequence, seconds, normalized=True)[-1]
            enabled = {module['id'] for module in base['modules'] if module['enabled']}
            paths = [m['path'] for m in (sequence.get('audio_reactivity') or {}).get('mappings', ())
                     if m['path'].split('.')[0] in enabled]
            dialog.set_active_paths(paths)
        except (ValueError, TypeError, KeyError) as error:
            dialog.set_responses(None)
            self.set_audio_reactivity_status(str(error))

    def reset_audio_reactivity_work(self):
        self.cancel_audio_reactivity()
        self.audio_reactivity_key = None
        self.audio_reactivity_available = False
        self.set_audio_reactivity_status('')
        if self.audio_reactivity_dialog:
            self.audio_reactivity_dialog.set_responses(None)
            self.audio_reactivity_dialog.hide()
