"""Local recent documents and durable, saved-state covers.

The browser only reads this index and its PNGs. Rendering is scheduled by open,
save or explicit folder import, never by opening or scrolling the browser.
"""
from collections import OrderedDict
from io import BytesIO
import hashlib
import json
import math
import os
from pathlib import Path
from queue import Empty, Full, Queue
import tempfile
import threading
import time

from PIL import Image
from PySide6.QtCore import QObject, QStandardPaths, QTimer, Signal
from media import Cancellation, Cancelled
from synth_study_thumbnails import ThumbnailCache, fitted_size

BOUNDS = (448, 288)
MAX_RECENTS = 256


def library_directory():
    state = os.environ.get('NEBULA_STATE_DIR')
    return (Path(state) if state else Path(QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.GenericDataLocation)) / 'Nebula Studio') / 'recent-projects'


def canonical(path):
    return str(Path(path).expanduser().resolve())


def signature(path):
    stat = Path(path).stat()
    return [stat.st_size, stat.st_mtime_ns]


def document_info(raw, path):
    if not isinstance(raw, dict): raise ValueError('Not a Nebula document')
    if raw.get('format') == 'nebula-montage': kind = 'Montage'
    elif raw.get('format') == 'nebula-composition': kind = 'Composition'
    elif isinstance(raw.get('states'), dict): kind = 'Sequence'
    elif isinstance(raw.get('modules'), list): kind = 'Preset'
    else: raise ValueError('Not a Nebula document')
    return dict(name=str(raw.get('name') or Path(path).stem), kind=kind)


class RecentProjectStore:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.cache = ThumbnailCache(self.directory / 'covers', disk_entries=MAX_RECENTS * 2)
        self.entries = {}
        try:
            data = json.loads((self.directory / 'index.json').read_text())
            if isinstance(data, dict) and data.get('version') == 1 and isinstance(data.get('projects'), list):
                for entry in data['projects'][:MAX_RECENTS]:
                    if not isinstance(entry, dict): continue
                    stamp = entry.get('signature')
                    seconds = entry.get('seconds')
                    if (isinstance(entry.get('path'), str) and entry['path']
                            and isinstance(entry.get('revision'), str) and len(entry['revision']) == 64
                            and isinstance(entry.get('updated'), (float, int)) and math.isfinite(entry['updated'])
                            and 0 <= entry['updated'] <= 253402214400
                            and isinstance(stamp, list) and len(stamp) == 2
                            and all(isinstance(v, int) and v >= 0 for v in stamp)
                            and (seconds is None or isinstance(seconds, (float, int)) and math.isfinite(seconds) and seconds >= 0)
                            and isinstance(entry.get('name'), str) and isinstance(entry.get('kind'), str)):
                        entry = dict(entry, path=canonical(entry['path']), seconds=seconds)
                        if not isinstance(entry.get('cover', ''), str): entry.pop('cover', None)
                        if not isinstance(entry.get('error', ''), str): entry.pop('error', None)
                        self.entries[entry['path']] = entry
        except (OSError, ValueError, KeyError, TypeError): pass

    def persist(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile('w', dir=self.directory, suffix='.tmp', delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(dict(version=1, projects=self.records()), stream, ensure_ascii=False)
            temporary.replace(self.directory / 'index.json')
        finally:
            if temporary: temporary.unlink(missing_ok=True)

    def records(self):
        return sorted(self.entries.values(), key=lambda e: e['updated'], reverse=True)

    def remember(self, path, seconds=None, *, imported=False):
        path = canonical(path)
        before = signature(path); data = Path(path).read_bytes()
        if signature(path) != before: raise ValueError('File changed while reading')
        info = document_info(json.loads(data), path)
        revision = hashlib.sha256(data).hexdigest()
        previous = self.entries.get(path, {})
        when = previous.get('seconds') if seconds is None else seconds
        when = max(0., float(when)) if when is not None and math.isfinite(float(when)) else None
        # Folder imports choose a useful frame, without replacing a chosen cover.
        if imported and not previous: when = None
        entry = dict(previous, **info, path=path, revision=revision, signature=before,
                     seconds=when, updated=(previous.get('updated', before[1]/1e9) if imported else time.time()))
        if revision != previous.get('revision') or when != previous.get('seconds'):
            entry['error'] = ''
        self.entries[path] = entry
        for old in self.records()[MAX_RECENTS:]: self.entries.pop(old['path'], None)
        self.persist()
        return entry

    def cover_key(self, entry):
        return hashlib.sha256(json.dumps([entry['path'], entry['revision'], entry['seconds'], BOUNDS]).encode()).hexdigest()

    def current_cover(self, entry):
        return entry.get('cover') == self.cover_key(entry)

    def accept(self, path, key, revision, data=None, error=''):
        entry = self.entries.get(path)
        if entry is None or entry['revision'] != revision or key != self.cover_key(entry): return False
        try:
            if signature(path) != entry['signature']: return False
        except OSError: return False
        if data:
            self.cache.put(key, data)
            entry['cover'] = key
        entry['error'] = error
        self.persist()
        return True

    def cover(self, entry):
        key = entry.get('cover', '')
        if len(key) != 64 or any(c not in '0123456789abcdef' for c in key): return None
        return self.cache.get(key)

    def remove(self, path):
        self.entries.pop(canonical(path), None); self.persist()


def packet_png(packet):
    size, raw = packet
    image = Image.frombytes('RGB', size, raw)
    image.thumbnail(BOUNDS, Image.Resampling.LANCZOS)
    output = BytesIO(); image.save(output, format='PNG')
    return output.getvalue()


def render_project_cover(path, seconds, cancel):
    """One small frame of a saved document, using the normal render pipeline."""
    from synth import load_synth, render_synth_frame
    from synth_composition import load_composition, compile_composition
    from synth_sequence import load_sequence, render_sequence_frame
    from synth_video import VideoFrameProvider
    raw = json.loads(Path(path).read_text()); kind = document_info(raw, path)['kind']
    cancel.check()
    if kind == 'Montage':
        from synth_montage import load_montage, MontageRenderer
        project = load_montage(path)
        total = sum(c['frames'] for c in project['clips'])
        if total == 0: raise ValueError('Empty montage')
        frame = min(total-1, round(seconds*project['fps']) if seconds is not None else total//3)
        with MontageRenderer(project, cancel, preview=True) as renderer:
            image = renderer.frame(frame, fitted_size(project['canvas'], BOUNDS))
    elif kind in ('Composition', 'Sequence'):
        sequence = compile_composition(load_composition(path)) if kind == 'Composition' else load_sequence(path)
        t = sequence['duration']/3 if seconds is None else min(seconds, max(0, sequence['duration']-1/sequence['fps']))
        with tempfile.TemporaryDirectory(prefix='nebula-project-cover-') as scratch:
            with VideoFrameProvider(preview=True, cancel=cancel, directory=scratch, budget=8*1024**2) as provider:
                image = render_sequence_frame(sequence, t, fitted_size(sequence['canvas'], BOUNDS), provider, cancel=cancel)
    else:
        preset = load_synth(path)
        image = render_synth_frame(preset, time_seconds=seconds or 0., size=fitted_size(preset, BOUNDS))
    cancel.check()
    return packet_png((image.size, image.convert('RGB').tobytes()))


class _CoverWorker:
    def __init__(self, renderer):
        self.renderer = renderer; self.condition = threading.Condition()
        self.jobs = OrderedDict(); self.results = Queue(maxsize=MAX_RECENTS)
        self.stopped = False; self.cancel = None; self.paused = False

    def run(self):
        while True:
            with self.condition:
                self.condition.wait_for(lambda: (self.jobs and not self.paused) or self.stopped)
                if self.stopped: return
                _, job = self.jobs.popitem(last=False)
                self.cancel = cancel = Cancellation()
            entry, key, packet = job; data = None; error = ''
            try:
                if signature(entry['path']) != entry['signature']: continue
                data = packet_png(packet) if packet else self.renderer(entry['path'], entry['seconds'], cancel)
                cancel.check()
            except Cancelled: continue
            except Exception as exc: error = str(exc)
            while not self.stopped:
                try:
                    self.results.put((entry['path'], key, entry['revision'], data, error), timeout=.1)
                    break
                except Full: continue

    def stop(self):
        with self.condition:
            self.stopped = True; self.jobs.clear()
            if self.cancel: self.cancel.cancel()
            self.condition.notify()


class RecentProjects(QObject):
    changed = Signal()

    def __init__(self, directory=None, parent=None, renderer=render_project_cover):
        super().__init__(parent)
        self.store = RecentProjectStore(directory or library_directory())
        self.busy = lambda: False
        self.worker = _CoverWorker(renderer)
        self.thread = threading.Thread(target=self.worker.run, name='Project covers', daemon=True)
        self.thread.start()
        self.timer = QTimer(self); self.timer.setInterval(100); self.timer.timeout.connect(self.deliver); self.timer.start()
        self.import_paths = []
        self.import_timer = QTimer(self); self.import_timer.setInterval(30); self.import_timer.timeout.connect(self._import_next)
        self.destroyed.connect(lambda *_args, worker=self.worker: worker.stop())
        # Resume interrupted saves at application startup, independently of the browser.
        for entry in self.store.records():
            if not entry.get('error') and (not self.store.current_cover(entry) or not self.store.cover(entry)): self.schedule(entry)

    def schedule(self, entry, packet=None):
        key = self.store.cover_key(entry)
        with self.worker.condition:
            if self.worker.stopped: return
            self.worker.jobs[entry['path']] = (dict(entry), key, packet)
            self.worker.condition.notify()

    def remember(self, path, seconds=None, packet=None, *, imported=False):
        try:
            entry = self.store.remember(path, seconds, imported=imported)
            if not self.store.current_cover(entry) or not self.store.cover(entry): self.schedule(entry, packet)
            self.changed.emit(); return True
        except (OSError, ValueError, TypeError): return False

    def deliver(self):
        with self.worker.condition:
            paused = bool(self.busy())
            if paused != self.worker.paused:
                self.worker.paused = paused
                self.worker.condition.notify()
        changed = False
        for _ in range(16):
            try: result = self.worker.results.get_nowait()
            except Empty: break
            try: changed = self.store.accept(*result) or changed
            except OSError: pass  # A cover failure never turns a successful project save into an error.
        if changed: self.changed.emit()

    def remove(self, path):
        try: self.store.remove(path)
        except OSError: return
        with self.worker.condition: self.worker.jobs.pop(canonical(path), None)
        self.changed.emit()

    def import_folder(self, folder):
        from synth_project_files import is_project_path
        try:
            paths = sorted((p for p in Path(folder).iterdir() if p.is_file() and is_project_path(p)),
                           key=lambda p: p.stat().st_mtime, reverse=True)
        except OSError: return
        self.import_paths = paths[:MAX_RECENTS]
        self.import_timer.start()

    def _import_next(self):
        if not self.import_paths:
            self.import_timer.stop(); return
        self.remember(self.import_paths.pop(0), imported=True)

    def close(self):
        self.deliver(); self.timer.stop(); self.import_timer.stop(); self.worker.stop()
