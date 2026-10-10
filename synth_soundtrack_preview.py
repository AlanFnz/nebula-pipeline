"""Project-clock soundtrack monitor, independent of rendered video frames.

Qt Multimedia is imported only when a local soundtrack is set. All public
methods must be called on the object's Qt thread. ``sync`` anchors a real-time
clock; callers must explicitly sync transport jumps, pauses and project loops.
The short timer enforces trim bounds while video decoding drops frames. Native
media seeking is approximate, and trimmed loops are not guaranteed gapless.
"""
from __future__ import annotations

import math
from copy import deepcopy
import time

from PySide6.QtCore import QObject, QTimer, QUrl, Signal


class AudioPreviewUnavailable(RuntimeError):
    """The platform cannot currently provide a soundtrack monitor."""


class _QtAudioBackend(QObject):
    readyChanged = Signal(bool)
    ended = Signal()
    error = Signal(str)

    def __init__(self, parent=None):
        try:
            from PySide6.QtMultimedia import QAudioOutput, QMediaDevices, QMediaPlayer
        except (ImportError, OSError) as exc:
            raise AudioPreviewUnavailable('Soundtrack preview is unavailable: Qt Multimedia is not installed.') from exc
        if not QMediaDevices.audioOutputs():
            raise AudioPreviewUnavailable('Soundtrack preview is unavailable: connect an audio output device.')
        super().__init__(parent)
        self._media_type = QMediaPlayer
        self._devices_type = QMediaDevices
        self._devices = QMediaDevices(self)
        self._output = QAudioOutput(self)
        self._player = QMediaPlayer(self)
        self._player.setAudioOutput(self._output)
        self._ready = False
        self._closed = False
        self._pending_source = None
        self._load_defer = QTimer(self)
        self._load_defer.setSingleShot(True)
        self._load_defer.setInterval(0)
        self._load_defer.timeout.connect(self._start_load)
        self._load_timeout = QTimer(self)
        self._load_timeout.setSingleShot(True)
        self._load_timeout.setInterval(10000)
        self._load_timeout.timeout.connect(self._timed_out)
        self._player.mediaStatusChanged.connect(self._status_changed)
        self._player.seekableChanged.connect(self._readiness_changed)
        self._player.hasAudioChanged.connect(self._readiness_changed)
        self._player.errorOccurred.connect(self._error_occurred)
        self._devices.audioOutputsChanged.connect(self._devices_changed)

    def load(self, path):
        if self._closed:
            return
        # First use can follow a native macOS file-picker return. Let Qt's
        # multimedia initialization and Cocoa dialog cleanup finish before
        # starting media I/O. One owned timer retains only the latest request.
        self._pending_source = str(path)
        self._load_defer.start()

    def _start_load(self):
        if self._closed or self._pending_source is None:
            return
        path, self._pending_source = self._pending_source, None
        self._load_timeout.start()
        self._player.setSource(QUrl.fromLocalFile(path))

    def _status_changed(self, status):
        if self._closed:
            return
        media = self._media_type.MediaStatus
        if status == media.InvalidMedia:
            self.error.emit(self._player.errorString() or 'The soundtrack cannot be decoded.')
            return
        self._readiness_changed()
        if status == media.EndOfMedia:
            self.ended.emit()

    def _readiness_changed(self, *_):
        if self._closed:
            return
        media = self._media_type.MediaStatus
        loaded = self._player.mediaStatus() in (
            media.LoadedMedia, media.BufferingMedia, media.BufferedMedia,
            media.StalledMedia, media.EndOfMedia,
        )
        ready = loaded and self._player.isSeekable() and self._player.hasAudio()
        if ready != self._ready:
            self._ready = ready
            if ready:
                self._load_timeout.stop()
            self.readyChanged.emit(ready)

    def _timed_out(self):
        if self._closed or self._ready:
            return
        if not self._player.hasAudio():
            self.error.emit('The soundtrack could not load a playable audio stream.')
        elif not self._player.isSeekable():
            self.error.emit('The soundtrack cannot be sought; relink to a local audio file.')
        else:
            self.error.emit('The soundtrack took too long to load; try reloading it.')

    def _error_occurred(self, _error, message):
        if not self._closed:
            self.error.emit(message or 'The soundtrack cannot be played.')

    def _devices_changed(self):
        if self._closed:
            return
        if not self._devices_type.audioOutputs():
            self.pause()
            self.error.emit('Audio output disconnected; reconnect it and reload the soundtrack.')
        else:
            self._output.setDevice(self._devices_type.defaultAudioOutput())

    def position_seconds(self):
        return self._player.position() / 1000.0

    def is_playing(self):
        return self._player.playbackState() == self._media_type.PlaybackState.PlayingState

    def seek(self, seconds):
        self._player.setPosition(round(seconds * 1000.0))

    def play(self):
        self._player.play()

    def pause(self):
        self._player.pause()

    def set_volume(self, value):
        self._output.setVolume(value)

    def set_muted(self, muted):
        self._output.setMuted(muted)

    def close(self):
        self._closed = True
        self._load_defer.stop()
        self._pending_source = None
        self._load_timeout.stop()
        self._player.stop()
        # A null URL stops media I/O and abandons an outstanding asynchronous load.
        self._player.setSource(QUrl())
        self._player.setAudioOutput(None)
        self.deleteLater()


def _source_time(track, seconds):
    from synth_soundtrack import soundtrack_source_time
    return soundtrack_source_time(track, seconds)


class SoundtrackPreview(QObject):
    """Monitor an authored track without changing its export selection.

    ``backend_factory(parent)`` is injectable and returns an object providing
    readyChanged(bool), ended(), error(str) signals and the methods implemented
    by _QtAudioBackend above. Construction/load may raise; those failures become
    status messages. There is no queue of sync requests or delayed play actions.
    Monitor volume and authored gain multiply on Qt's linear 0..1 output scale.
    """
    statusChanged = Signal(str)
    DRIFT_SECONDS = 0.18
    CORRECTION_INTERVAL = 0.75

    def __init__(self, parent=None, *, backend_factory=None, source_time=None,
                 clock=time.monotonic):
        super().__init__(parent)
        self._backend_factory = backend_factory or _QtAudioBackend
        self._source_time = source_time or _source_time
        self._clock = clock
        self._backend = None
        self._connections = []
        self._track = None
        self._key = None
        self._ready = False
        self._failed = False
        self._closed = False
        self._status = ''
        self._volume = 1.0
        self._muted = False
        self._playing = False
        self._project_seconds = 0.0
        self._anchor = self._clock()
        self._last_target = None
        self._last_cycle = None
        self._last_seek = -math.inf
        self._needs_seek = True
        self._native_ended = False
        self._timer = QTimer(self)
        self._timer.setInterval(25)
        self._timer.timeout.connect(self._tick)

    @property
    def status(self):
        return self._status

    def _set_status(self, value):
        if value != self._status:
            self._status = value
            self.statusChanged.emit(value)

    def set_track(self, track):
        if self._closed:
            return
        track = deepcopy(track) if track else None
        identity = track.get('identity') if track else None
        key = (track.get('id'), str(track.get('path', '')),
               repr(identity)) if track else None
        if key == self._key and track == self._track:
            return
        path = None
        if track is not None:
            try:
                from synth_soundtrack import check_soundtrack
                path = check_soundtrack(track)
            except (ValueError, OSError) as exc:
                self._track, self._key = track, key
                self._dispose_backend()
                self._playing = False
                self._timer.stop()
                self._failed = True
                self._set_status(str(exc))
                return
        same_source = key == self._key and self._backend is not None
        changed_timing = track is not None and self._track is not None and any(
            track.get(field) != self._track.get(field)
            for field in ('in', 'out', 'offset', 'end_mode')
        )
        self._track = track
        self._key = key
        if same_source:
            self._apply_volume()
            if changed_timing:
                self._needs_seek = True
                self._last_cycle = None
                self._apply(force=True)
            return
        self._dispose_backend()
        self._playing = False
        self._timer.stop()
        self._last_target = self._last_cycle = None
        self._needs_seek = True
        self._native_ended = False
        self._failed = False
        if track is None:
            self._set_status('')
            return
        self._set_status('Loading soundtrack…')
        try:
            backend = self._backend_factory(self)
            self._backend = backend
            for signal, callback in (
                (backend.readyChanged, lambda ready: self._on_ready(backend, ready)),
                (backend.ended, lambda: self._on_ended(backend)),
                (backend.error, lambda message: self._on_error(backend, message)),
            ):
                signal.connect(callback)
                self._connections.append((signal, callback))
            self._apply_volume()
            backend.load(path)
        except Exception as exc:
            self._dispose_backend()
            self._failed = True
            self._set_status(str(exc) or 'Soundtrack preview is unavailable.')

    def sync(self, project_seconds, playing, *, force=False):
        if self._closed:
            return
        seconds = float(project_seconds)
        if not math.isfinite(seconds):
            raise ValueError('Project time must be finite.')
        now = self._clock()
        previous = self._current_project(now)
        discontinuity = abs(seconds - previous) > self.DRIFT_SECONDS
        changed_play = bool(playing) != self._playing
        self._project_seconds = max(0.0, seconds)
        self._anchor = now
        self._playing = bool(playing)
        if self._playing and self._track is not None and not self._failed:
            self._timer.start()
        else:
            self._timer.stop()
        self._apply(force=force or discontinuity or changed_play)

    def set_monitor_volume(self, value):
        value = float(value)
        if not math.isfinite(value):
            raise ValueError('Monitor volume must be finite.')
        self._volume = min(1.0, max(0.0, value))
        self._apply_volume()

    def set_monitor_muted(self, muted):
        self._muted = bool(muted)
        self._apply_volume()

    def _apply_volume(self):
        if self._backend is not None:
            gain = float(self._track.get('gain', 1.0))
            self._backend.set_volume(min(1.0, max(0.0, gain * self._volume)))
            self._backend.set_muted(self._muted)

    def _current_project(self, now=None):
        elapsed = max(0.0, (self._clock() if now is None else now) - self._anchor)
        return self._project_seconds + (elapsed if self._playing else 0.0)

    def _tick(self):
        self._apply()

    def _apply(self, *, force=False):
        backend = self._backend
        if backend is None or not self._ready or self._failed or self._track is None:
            if force:
                self._needs_seek = True
            return
        now = self._clock()
        project = self._current_project(now)
        target = self._source_time(self._track, project)
        if target is None:
            if backend.is_playing():
                backend.pause()
            self._last_target = self._last_cycle = None
            self._needs_seek = True
            return
        cycle = 0
        if self._track.get('end_mode') == 'loop':
            span = float(self._track['out']) - float(self._track['in'])
            cycle = math.floor(max(0.0, project - float(self._track.get('offset', 0.0))) / span)
        wrapped = self._last_cycle is not None and cycle != self._last_cycle
        scrubbed = not self._playing and target != self._last_target
        drift = not self._native_ended and abs(backend.position_seconds() - target) > self.DRIFT_SECONDS
        seek = force or self._needs_seek or wrapped or scrubbed or (
            drift and now - self._last_seek >= self.CORRECTION_INTERVAL
        )
        if seek:
            backend.seek(target)
            self._last_seek = now
            self._needs_seek = False
            self._native_ended = False
        self._last_target = target
        self._last_cycle = cycle
        if self._playing:
            if not backend.is_playing() and not self._native_ended:
                backend.play()
        elif backend.is_playing():
            backend.pause()

    def _on_ready(self, backend, ready):
        if backend is not self._backend or self._closed or self._failed:
            return
        self._ready = bool(ready)
        if ready:
            self._set_status('')
            self._apply(force=True)
        else:
            self._set_status('Loading soundtrack…')

    def _on_ended(self, backend):
        if backend is self._backend and not self._closed:
            # Early native EOF must not repeatedly restart a silence track. A
            # loop is positioned from the clock, rather than reset to file zero.
            if self._track and self._track.get('end_mode') == 'loop':
                self._apply(force=True)
            else:
                self._native_ended = True

    def _on_error(self, backend, message):
        if backend is not self._backend or self._closed:
            return
        self._failed = True
        self._ready = False
        self._timer.stop()
        backend.pause()
        self._set_status('Soundtrack preview unavailable: ' + str(message))

    def _dispose_backend(self):
        backend, self._backend = self._backend, None
        self._ready = False
        for signal, callback in self._connections:
            try:
                signal.disconnect(callback)
            except (RuntimeError, TypeError):
                pass
        self._connections.clear()
        if backend is not None:
            backend.close()

    def close(self):
        if self._closed:
            return
        self._closed = True
        self._timer.stop()
        self._playing = False
        self._track = None
        self._dispose_backend()
        self._set_status('')
