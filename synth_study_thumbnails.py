"""Bounded still previews for the library, independent of document preview work."""
from collections import OrderedDict, deque
import hashlib
from io import BytesIO
import json
from pathlib import Path
from queue import Empty, Full, Queue
import tempfile
import threading
import sys

from PIL import Image, ImageStat
from PySide6.QtCore import QObject, QStandardPaths, QTimer, Signal

from media import Cancellation, Cancelled
from synth_composition import compile_composition
from synth_sequence import render_sequence_frame
from synth_studies import study_composition
from synth_video import VideoFrameProvider

THUMBNAIL_VERSION = 1
MAX_PENDING = 12


def fitted_size(canvas, bounds):
    ratio = min(bounds[0] / canvas['width'], bounds[1] / canvas['height'])
    return tuple(max(1, round(canvas[key] * ratio)) for key in ('width', 'height'))


def _identity(path):
    path = Path(path)
    try:
        stat = path.stat()
        return [str(path.resolve()), stat.st_size, stat.st_mtime_ns]
    except OSError:
        return [str(path.absolute()), 'missing']


def thumbnail_key(project, size, directory=None):
    """Include recipe, source identity, bundled assets and renderer implementation."""
    base = Path(__file__).parent
    paths = list(base.glob('synth*.py')) + list((base / 'assets').rglob('*')) + list((base / 'presets').glob('*.json'))
    def references(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if isinstance(child, str) and (key == 'path' or key.endswith('.path')):
                    paths.append(Path(child))
                else: references(child)
        elif isinstance(value, list):
            for child in value: references(child)
    references(project)
    build = _identity(sys.executable) if getattr(sys, 'frozen', False) else None
    payload = [THUMBNAIL_VERSION, build, project, size, str(Path(directory).resolve()) if directory else None,
               [_identity(path) for path in sorted(set(paths)) if not path.is_dir()]]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def render_thumbnail(project, bounds, cancel=None, frame_provider=None):
    cancel = cancel or Cancellation()
    cancel.check()
    sequence = compile_composition(project)
    size = fitted_size(project['canvas'], bounds)
    image = render_sequence_frame(sequence, sequence['duration'] / 3, size, frame_provider)
    cancel.check()
    # At most one deterministic alternate; a dark intentional composition stays dark.
    if max(ImageStat.Stat(image.convert('RGB')).mean) < 3:
        image = render_sequence_frame(sequence, sequence['duration'] * 2 / 3, size, frame_provider)
    cancel.check()
    output = BytesIO(); image.save(output, format='PNG')
    return output.getvalue()


class ThumbnailCache:
    def __init__(self, directory, memory_entries=64, disk_bytes=64 * 1024**2, disk_entries=256):
        self.directory = Path(directory)
        self.memory_entries, self.disk_bytes, self.disk_entries = memory_entries, disk_bytes, disk_entries
        self.memory = OrderedDict()

    def get(self, key):
        if key in self.memory:
            self.memory.move_to_end(key)
            return self.memory[key]
        try:
            path = self.directory / (key + '.png')
            data = path.read_bytes()
            with Image.open(BytesIO(data)) as image: image.verify()
            path.touch()
            self._remember(key, data)
            return data
        except (OSError, ValueError): return None

    def _remember(self, key, data):
        self.memory[key] = data; self.memory.move_to_end(key)
        while len(self.memory) > self.memory_entries: self.memory.popitem(last=False)

    def put(self, key, data):
        self._remember(key, data)
        temporary = None
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=self.directory, suffix='.tmp', delete=False) as stream:
                temporary = Path(stream.name); stream.write(data)
            temporary.replace(self.directory / (key + '.png'))
            files = sorted(self.directory.glob('*.png'), key=lambda path: path.stat().st_mtime_ns, reverse=True)
            total = 0
            for index, path in enumerate(files):
                total += path.stat().st_size
                if index >= self.disk_entries or total > self.disk_bytes: path.unlink(missing_ok=True)
        except OSError: pass
        finally:
            if temporary is not None:
                try: temporary.unlink(missing_ok=True)
                except OSError: pass


class _WorkerState:
    def __init__(self, directory, cache, renderer):
        self.directory, self.cache, self.renderer = directory, cache, renderer
        self.condition = threading.Condition()
        self.jobs = deque()
        self.results = Queue(maxsize=1)
        self.cancel = None
        self.active_job = None
        self.generation = 0
        self.stopped = False

    def run(self):
        while True:
            with self.condition:
                self.condition.wait_for(lambda: self.jobs or self.stopped)
                if self.stopped: return
                job = self.jobs.popleft()
                generation, identifier, bounds = job
                cancel = self.cancel = Cancellation(); self.active_job = job
            data, error = None, ''
            try:
                project = study_composition(identifier, self.directory)
                key = thumbnail_key(project, bounds, self.directory)
                data = self.cache.get(key)
                if data is None:
                    # Each job owns decoding/proxy/mask state; nothing touches the document cache.
                    with tempfile.TemporaryDirectory(prefix='nebula-study-') as scratch:
                        with VideoFrameProvider(preview=True, cancel=cancel, directory=scratch, budget=8 * 1024**2) as provider:
                            data = self.renderer(project, bounds, cancel, provider)
                    cancel.check(); self.cache.put(key, data)
            except Cancelled: pass
            except Exception as exception:
                error = f'Preview unavailable: {exception}'
            if not cancel.event.is_set():
                while not cancel.event.is_set():
                    try:
                        self.results.put((generation, identifier, bounds, data, error), timeout=.05)
                        break
                    except Full: continue
            with self.condition:
                self.active_job = None; self.cancel = None


class StudyThumbnailService(QObject):
    """One cancellable worker, twelve pending jobs and one pending GUI delivery."""
    ready = Signal(int, str, object, object, str)

    def __init__(self, directory=None, parent=None, cache_directory=None, renderer=render_thumbnail):
        super().__init__(parent)
        cache_directory = cache_directory or Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation)) / 'NebulaStudio' / 'study-thumbnails'
        self.state = _WorkerState(directory, ThumbnailCache(cache_directory), renderer)
        self.generation = 0
        self.timer = QTimer(self); self.timer.setInterval(30); self.timer.timeout.connect(self._deliver)
        self.timer.start()
        self.thread = threading.Thread(target=self.state.run, name='Study thumbnails', daemon=True)
        self.thread.start()
        self._state_holder = [self.state]
        self.destroyed.connect(lambda *_args, holder=self._state_holder: _stop_state(holder[0]))

    def start(self):
        """Restart a closed, reusable browser with an isolated new worker state."""
        if not self.state.stopped: return
        old = self.state
        self.state = _WorkerState(old.directory, ThumbnailCache(old.cache.directory,
                                  old.cache.memory_entries, old.cache.disk_bytes, old.cache.disk_entries), old.renderer)
        self._state_holder[0] = self.state
        self.thread = threading.Thread(target=self.state.run, name='Study thumbnails', daemon=True)
        self.thread.start(); self.timer.start()

    @property
    def pending_count(self):
        with self.state.condition: return len(self.state.jobs)

    def reset(self):
        self.generation += 1
        with self.state.condition:
            self.state.jobs.clear()
            if self.state.cancel: self.state.cancel.cancel()
        return self.generation

    def request(self, jobs):
        """Replace warming with selected-first visible work, bounded by MAX_PENDING."""
        with self.state.condition:
            if self.state.stopped: return
            wanted = [(self.generation, identifier, tuple(bounds)) for identifier, bounds in jobs][:MAX_PENDING]
            self.state.jobs = deque(job for job in wanted if job != self.state.active_job)
            if self.state.active_job and self.state.active_job not in wanted and self.state.cancel:
                self.state.cancel.cancel()
            self.state.condition.notify()

    def _deliver(self):
        try: result = self.state.results.get_nowait()
        except Empty: return
        if result[0] == self.generation: self.ready.emit(*result)

    def close(self):
        self.reset(); self.timer.stop()
        _stop_state(self.state)


def _stop_state(state):
    with state.condition:
        state.jobs.clear(); state.stopped = True
        if state.cancel: state.cancel.cancel()
        state.condition.notify()
