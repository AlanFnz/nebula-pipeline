"""Temporary, lossless RGB storage for explicitly prepared complete previews."""
import shutil
import tempfile
from pathlib import Path


class DiskFrames:
    def __init__(self, size, count):
        self.size = tuple(size)
        self.frame_bytes = size[0] * size[1] * 3
        required = self.frame_bytes * count
        if shutil.disk_usage(tempfile.gettempdir()).free < required + 64 * 1024**2:
            raise OSError(f'Full preview needs {required / 1024**2:.0f} MB of temporary disk space. Free space and try again.')
        self.folder = tempfile.TemporaryDirectory(prefix='nebula-full-preview-')
        self.frames = set()

    def path(self, frame):
        return Path(self.folder.name) / f'{frame}.rgb'

    def put(self, frame, packet):
        size, raw = packet
        if tuple(size) != self.size or len(raw) != self.frame_bytes:
            raise ValueError('Preview frame has unexpected dimensions')
        path = self.path(frame)
        try:
            path.write_bytes(raw)
        except OSError:
            path.unlink(missing_ok=True)
            self.frames.discard(frame)
            raise
        self.frames.add(frame)

    def get(self, frame):
        if frame not in self.frames: return None
        try: raw = self.path(frame).read_bytes()
        except OSError: raw = b''
        if len(raw) != self.frame_bytes:
            self.frames.discard(frame)
            return None
        return self.size, raw

    def retain(self, predicate):
        for frame in list(self.frames):
            if not predicate(frame):
                self.path(frame).unlink(missing_ok=True)
                self.frames.remove(frame)

    def close(self):
        self.folder.cleanup()
