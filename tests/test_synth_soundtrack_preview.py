"""Transport correctness without codec latency or physical audio devices."""
import copy
import math
import os
import sys
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from synth_soundtrack_preview import AudioPreviewUnavailable, SoundtrackPreview, _QtAudioBackend


class Clock:
    now = 100.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class FakeBackend(QObject):
    readyChanged = Signal(bool)
    ended = Signal()
    error = Signal(str)

    def __init__(self, parent, clock):
        super().__init__(parent)
        self.clock = clock
        self.loaded = []
        self.seeks = []
        self.plays = 0
        self.pauses = 0
        self.closed = False
        self.playing = False
        self.position = 0.0
        self.anchor = clock()
        self.volume = 1.0
        self.muted = False

    def load(self, path):
        self.loaded.append(str(path))

    def position_seconds(self):
        return self.position + (self.clock() - self.anchor if self.playing else 0)

    def is_playing(self):
        return self.playing

    def seek(self, seconds):
        self.position = seconds
        self.anchor = self.clock()
        self.seeks.append(seconds)

    def play(self):
        self.position = self.position_seconds()
        self.anchor = self.clock()
        self.playing = True
        self.plays += 1

    def pause(self):
        self.position = self.position_seconds()
        self.playing = False
        self.pauses += 1

    def set_volume(self, value):
        self.volume = value

    def set_muted(self, value):
        self.muted = value

    def close(self):
        self.pause()
        self.closed = True


def source_time(track, project):
    elapsed = project - track['offset']
    span = track['out'] - track['in']
    if elapsed < 0 or (track['end_mode'] == 'silence' and elapsed >= span):
        return None
    return track['in'] + (elapsed % span if track['end_mode'] == 'loop' else elapsed)


@pytest.fixture
def monitor(tmp_path):
    app = QApplication.instance() or QApplication([])
    clock = Clock()
    backends = []

    def factory(parent):
        backend = FakeBackend(parent, clock)
        backends.append(backend)
        return backend

    path = tmp_path / 'tone.wav'
    path.touch()
    track = dict(id='one', name='Tone', path=str(path), duration=10.0,
                 sample_rate=48000, channels=1, **{'in': 2.0, 'out': 5.0},
                 offset=1.0, end_mode='silence', gain=0.8, export_audio='soundtrack')
    preview = SoundtrackPreview(backend_factory=factory, source_time=source_time, clock=clock)
    yield preview, track, backends, clock
    preview.close()
    app.processEvents()


def loaded(monitor):
    preview, track, backends, clock = monitor
    preview.set_track(track)
    backend = backends[-1]
    backend.readyChanged.emit(True)
    return preview, track, backend, clock


def test_lazy_backend_and_setting_track_never_starts(monitor):
    preview, track, backends, _ = monitor
    assert backends == []
    preview.set_track(track)
    assert len(backends) == 1 and not backends[0].playing
    backends[0].readyChanged.emit(True)
    assert not backends[0].playing
    assert preview.status == ''


def test_late_load_applies_latest_seek_and_pause(monitor):
    preview, track, backends, clock = monitor
    preview.set_track(track)
    backend = backends[-1]
    preview.sync(1.5, True)
    preview.sync(2.1, True, force=True)
    preview.sync(2.7, False)
    clock.advance(5)
    backend.readyChanged.emit(True)
    assert backend.seeks == [pytest.approx(3.7)]
    assert backend.plays == 0


def test_late_load_uses_elapsed_real_time_while_playing(monitor):
    preview, track, backends, clock = monitor
    preview.set_track(track)
    preview.sync(1.0, True)
    clock.advance(0.6)
    backend = backends[-1]
    backend.readyChanged.emit(True)
    assert backend.seeks == [pytest.approx(2.6)]
    assert backend.playing


def test_continuous_clock_does_not_seek_each_video_frame(monitor):
    preview, _, backend, clock = loaded(monitor)
    preview.sync(1.0, True)
    for index in range(1, 51):
        clock.advance(0.02)
        preview.sync(1 + index * 0.02, True)
    assert backend.seeks == [pytest.approx(2.0)]
    assert backend.plays == 1


def test_drift_correction_has_tolerance_and_cooldown(monitor):
    preview, _, backend, clock = loaded(monitor)
    preview.sync(1.0, True)
    clock.advance(0.3)
    backend.position -= 0.1
    preview._tick()
    assert len(backend.seeks) == 1
    backend.position -= 0.3
    preview._tick()
    assert len(backend.seeks) == 1
    clock.advance(0.5)
    preview._tick()
    assert backend.seeks[-1] == pytest.approx(2.8)
    assert len(backend.seeks) == 2


def test_project_jump_loop_and_paused_scrub_seek_immediately(monitor):
    preview, _, backend, _ = loaded(monitor)
    preview.sync(2.0, True)
    preview.sync(3.0, True)
    preview.sync(1.0, True)
    assert backend.seeks == [3.0, 4.0, 2.0]
    preview.sync(1.1, False)
    preview.sync(1.11, False)
    assert backend.seeks[-1] == pytest.approx(2.11)
    assert not backend.playing


def test_offset_and_trim_silence_follow_timer_without_video_ticks(monitor):
    preview, _, backend, clock = loaded(monitor)
    preview.sync(0.0, True)
    assert not backend.playing
    clock.advance(1.05)
    preview._tick()
    assert backend.playing and backend.seeks[-1] == pytest.approx(2.05)
    clock.advance(3.0)
    preview._tick()
    assert not backend.playing
    assert backend.plays == 1
    preview.sync(1.5, False)
    assert backend.seeks[-1] == pytest.approx(2.5)


def test_trimmed_loop_and_skipped_cycles_use_project_clock(monitor):
    preview, track, backends, clock = monitor
    track['end_mode'] = 'loop'
    preview.set_track(track)
    backend = backends[-1]
    backend.readyChanged.emit(True)
    preview.sync(3.9, True)
    clock.advance(0.2)
    preview._tick()
    assert backend.seeks == [pytest.approx(4.9), pytest.approx(2.1)]
    clock.advance(6.0)
    preview._tick()
    assert backend.seeks[-1] == pytest.approx(2.1)
    assert len(backend.seeks) == 3


def test_native_end_loop_restarts_at_clock_position(monitor):
    preview, track, backends, clock = monitor
    track.update(end_mode='loop', out=10.0)
    preview.set_track(track)
    backend = backends[-1]
    backend.readyChanged.emit(True)
    preview.sync(8.9, True)
    clock.advance(0.2)
    backend.playing = False
    backend.ended.emit()
    assert backend.seeks[-1] == pytest.approx(2.1)
    assert backend.playing


def test_repeated_track_updates_gain_without_reloading(monitor):
    preview, track, backends, _ = monitor
    preview.set_track(track)
    preview.set_track(copy.deepcopy(track))
    backend = backends[-1]
    backend.readyChanged.emit(True)
    preview.sync(1.0, True)
    changed = dict(track, gain=0.5, export_audio='silent')
    preview.set_track(changed)
    assert len(backends) == 1 and len(backend.loaded) == 1
    assert backend.playing and backend.volume == 0.5
    assert len(backend.seeks) == 1


def test_trim_update_seeks_current_project_without_reload(monitor):
    preview, track, backend, _ = loaded(monitor)
    preview.sync(1.5, True)
    changed = dict(track, **{'in': 1.0, 'out': 4.0})
    preview.set_track(changed)
    assert backend.seeks[-1] == pytest.approx(1.5)
    assert len(backend.loaded) == 1 and backend.playing


def test_monitor_volume_mute_dont_edit_authored_track(monitor):
    preview, track, backend, _ = loaded(monitor)
    before = copy.deepcopy(track)
    preview.set_monitor_volume(0.5)
    preview.set_monitor_muted(True)
    preview.sync(1.0, True)
    assert backend.volume == pytest.approx(0.4)
    assert backend.muted and backend.playing
    preview.set_monitor_muted(False)
    assert not backend.muted and backend.volume == pytest.approx(0.4)
    assert track == before


def test_replacement_ignores_stale_load_error_and_end(monitor):
    preview, track, backends, _ = monitor
    preview.set_track(track)
    old = backends[-1]
    preview.sync(2.0, True)
    preview.set_track(dict(track, id='two'))
    current = backends[-1]
    assert old.closed
    old.readyChanged.emit(True)
    old.error.emit('obsolete load failed')
    old.ended.emit()
    assert preview.status == 'Loading soundtrack…'
    current.readyChanged.emit(True)
    assert not current.playing and preview.status == ''
    preview.sync(2.0, True)
    assert current.playing


def test_missing_file_and_unavailable_backend_have_status(monitor):
    preview, track, backends, _ = monitor
    preview.set_track(dict(track, path=track['path'] + '.missing'))
    assert backends == [] and 'relink' in preview.status.lower()
    def unavailable(parent):
        raise AudioPreviewUnavailable('No output device')
    preview._backend_factory = unavailable
    preview.set_track(track)
    assert preview.status == 'No output device'
    preview.sync(1.0, True)
    assert not preview._timer.isActive()


def test_backend_error_stops_monitor_until_track_changes(monitor):
    preview, _, backend, clock = loaded(monitor)
    preview.sync(1.0, True)
    backend.error.emit('Cannot decode audio')
    assert not backend.playing and 'Cannot decode audio' in preview.status
    assert not preview._timer.isActive()
    clock.advance(1)
    preview.sync(2.0, True)
    backend.readyChanged.emit(True)
    assert not backend.playing


def test_remove_and_close_cancel_playback_and_late_events(monitor):
    preview, track, backend, _ = loaded(monitor)
    preview.sync(1.0, True)
    preview.set_track(None)
    assert backend.closed and not preview._timer.isActive() and preview.status == ''
    preview.set_track(track)
    current = preview._backend
    preview.close()
    preview.close()
    current.readyChanged.emit(True)
    preview.sync(1.0, True)
    assert current.closed and current.plays == 0 and preview.status == ''


@pytest.mark.parametrize('value', [math.nan, math.inf, -math.inf])
def test_nonfinite_clock_or_volume_rejected(monitor, value):
    preview, _, _, _ = monitor
    with pytest.raises(ValueError):
        preview.sync(value, True)
    with pytest.raises(ValueError):
        preview.set_monitor_volume(value)


def test_file_identity_change_requires_relink_then_reloads(monitor):
    preview, track, backends, _ = monitor
    from pathlib import Path
    path = Path(track['path'])
    stat = path.stat()
    track['identity'] = dict(size=stat.st_size, mtime_ns=stat.st_mtime_ns)
    preview.set_track(track)
    old = backends[-1]
    path.write_bytes(b'new file contents')
    preview.set_track(dict(track, gain=0.4))
    assert old.closed and 'changed' in preview.status
    assert len(backends) == 1
    stat = path.stat()
    preview.set_track(dict(track, identity=dict(size=stat.st_size, mtime_ns=stat.st_mtime_ns)))
    assert len(backends) == 2


def test_early_native_end_of_silence_track_does_not_restart(monitor):
    preview, _, backend, clock = loaded(monitor)
    preview.sync(2.0, True)
    backend.playing = False
    backend.ended.emit()
    clock.advance(1)
    preview._tick()
    assert backend.plays == 1
    preview.sync(1.0, True, force=True)
    assert backend.playing and backend.plays == 2


def test_sync_does_no_media_file_io(monitor, monkeypatch):
    preview, _, backend, clock = loaded(monitor)
    def forbidden(*args, **kwargs):
        raise AssertionError('file identity checks must not run on timeline ticks')
    monkeypatch.setattr('synth_soundtrack.check_soundtrack', forbidden)
    preview.sync(1.0, True)
    clock.advance(.1)
    preview._tick()
    assert backend.playing


@pytest.fixture
def deferred_qt_backend(monkeypatch):
    """Exercise real Qt scheduling with a decoder that records source calls."""
    app = QApplication.instance() or QApplication([])
    class Player(QObject):
        mediaStatusChanged = Signal(object)
        seekableChanged = Signal(bool)
        hasAudioChanged = Signal(bool)
        errorOccurred = Signal(object, str)

        def __init__(self, parent):
            super().__init__(parent)
            self.sources = []

        def setSource(self, source):
            self.sources.append(source.toLocalFile())

        def setAudioOutput(self, output):
            pass

        def stop(self):
            pass

    class Devices(QObject):
        audioOutputsChanged = Signal()

        @staticmethod
        def audioOutputs():
            return [object()]

    monkeypatch.setitem(sys.modules, 'PySide6.QtMultimedia', SimpleNamespace(
        QMediaPlayer=Player, QAudioOutput=QObject, QMediaDevices=Devices))
    backends = []
    def factory():
        backend = _QtAudioBackend()
        backends.append(backend)
        return backend
    yield app, factory
    for backend in backends:
        if not backend._closed:
            backend.close()
    app.processEvents()


def test_qt_load_starts_after_event_turn_and_retains_only_latest(deferred_qt_backend):
    app, factory = deferred_qt_backend
    backend = factory()
    backend.load('/tmp/old.wav')
    backend.load('/tmp/latest.wav')
    assert backend._player.sources == []
    assert not backend._load_timeout.isActive()
    app.processEvents()
    assert backend._player.sources == ['/tmp/latest.wav']
    assert backend._load_timeout.isActive()
    app.processEvents()
    assert backend._player.sources == ['/tmp/latest.wav']


def test_qt_close_cancels_deferred_source_without_starting_io(deferred_qt_backend):
    app, factory = deferred_qt_backend
    backend = factory()
    player = backend._player
    backend.load('/tmp/cancelled.wav')
    backend.close()
    backend.load('/tmp/after-close.wav')
    app.processEvents()
    assert player.sources == ['']  # Only the null URL that abandons media I/O.


def test_qt_replacement_cancels_old_deferred_source(deferred_qt_backend):
    app, factory = deferred_qt_backend
    old = factory()
    old_player = old._player
    old.load('/tmp/replaced.wav')
    old.close()
    current = factory()
    current.load('/tmp/current.wav')
    app.processEvents()
    assert old_player.sources == ['']
    assert current._player.sources == ['/tmp/current.wav']


@pytest.mark.skipif(os.environ.get('NEBULA_AUDIO_SMOKE') != '1',
                    reason='Opt-in native codec/audio device smoke test')
def test_native_backend_muted_tone_load_pause_seek_and_loop(tmp_path):
    import struct
    import wave
    from PySide6.QtCore import QEventLoop, QTimer
    app = QApplication.instance() or QApplication([])
    path = tmp_path / 'native-tone.wav'
    with wave.open(str(path), 'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(48000)
        output.writeframes(b''.join(struct.pack('<h', round(400 * math.sin(2 * math.pi * 440 * i / 48000)))
                                   for i in range(96000)))
    track = dict(id='native', name='Tone', path=str(path), duration=2., sample_rate=48000,
                 channels=1, **{'in': .25, 'out': 1.25}, offset=0., end_mode='loop',
                 gain=.5, export_audio='soundtrack')
    preview = SoundtrackPreview()
    loop = QEventLoop()
    poll = QTimer()
    poll.setInterval(10)
    poll.timeout.connect(lambda: loop.quit() if preview._ready else None)
    timeout = QTimer()
    timeout.setSingleShot(True)
    timeout.timeout.connect(loop.quit)
    try:
        preview.set_monitor_muted(True)
        preview.set_track(track)
        if preview._backend is None and 'output device' in preview.status:
            pytest.skip(preview.status)
        preview.sync(.5, False, force=True)
        poll.start()
        timeout.start(3000)
        loop.exec()
        poll.stop()
        timeout.stop()
        assert preview._ready, preview.status
        backend = preview._backend
        assert not backend.is_playing()
        assert backend.position_seconds() == pytest.approx(.75, abs=.03)
        preview.sync(.9, True, force=True)
        timeout.start(400)
        loop.exec()
        assert backend.is_playing()
        assert .25 <= backend.position_seconds() < 1.25
        preview.sync(.2, False, force=True)
        assert not backend.is_playing()
        assert backend.position_seconds() == pytest.approx(.45, abs=.03)
        assert preview.status == ''
    finally:
        preview.close()
        app.processEvents()
