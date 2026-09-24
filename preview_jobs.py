"""Bounded caches and a cancellable, current-frame-first preview worker."""
import json
import time
from collections import OrderedDict

from PySide6.QtCore import QObject, Signal

from engine import render_frame
from media import Cancelled, decode_frames, dimensions


class Events(QObject):
    message = Signal(int, str, object)


class ByteCache:
    def __init__(self, budget):
        self.budget = budget
        self.size = 0
        self.items = OrderedDict()

    def get(self, key):
        if key not in self.items:
            return None
        self.items.move_to_end(key)
        return self.items[key][0]

    def put(self, key, value, size):
        if key in self.items:
            self.size -= self.items.pop(key)[1]
        if size > self.budget:
            return
        self.items[key] = (value, size)
        self.size += size
        while self.size > self.budget:
            self.size -= self.items.popitem(last=False)[1][1]


class PreviewWorker:
    """Used exclusively on one executor thread; no GUI objects in caches."""
    def __init__(self, events):
        self.events = events
        self.sources = ByteCache(64 * 1024 * 1024)
        self.renders = ByteCache(128 * 1024 * 1024)

    def run(self, generation, info, params, snapshot, frame, start, count, edge, stage, cancel):
        began = time.perf_counter()
        signature = (info["path"], info["identity"], params["fps"], edge)
        settings = json.dumps(params, sort_keys=True)
        reference = json.dumps(snapshot, sort_keys=True) if snapshot else None
        scale = dimensions(info, edge)[0] / info["width"]

        def emit(index, source=None):
            cancel.check()
            key = (signature, settings, reference, stage, index)
            packet = self.renders.get(key)
            if packet is None:
                if source is None:
                    source = self.sources.get((signature, index))
                if source is None:
                    return False
                current = render_frame(source, params, index, stage, scale)
                cancel.check()
                a = render_frame(source, snapshot, index, stage, scale).tobytes() if snapshot else None
                packet = (current.size, current.tobytes(), a)
                self.renders.put(key, packet, len(packet[1]) + (len(a) if a else 0))
            cancel.check()
            self.events.message.emit(generation, "frame", (index, packet, time.perf_counter() - began))
            return True

        try:
            if not emit(frame):
                found = False
                for index, source in decode_frames(info, params["fps"], frame, 1, edge, cancel):
                    self.sources.put((signature, index), source, source.width * source.height * 3)
                    emit(index, source)
                    found = True
                if not found:
                    raise ValueError("No frame at this time. Try an earlier position.")
            cancel.check()
            missing = []
            for index in range(start, start + count):
                if index != frame and not emit(index):
                    missing.append(index)
            if missing:
                for index, source in decode_frames(info, params["fps"], missing[0], missing[-1] - missing[0] + 1, edge, cancel):
                    self.sources.put((signature, index), source, source.width * source.height * 3)
                    if index != frame:
                        emit(index, source)
            cancel.check()
            self.events.message.emit(generation, "done", time.perf_counter() - began)
        except Cancelled:
            pass
        except Exception as exc:
            self.events.message.emit(generation, "error", str(exc))
