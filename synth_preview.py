"""Bounded preview cache and absolute-time scope planning; never export data."""
from collections import OrderedDict
from dataclasses import dataclass
import math


class PreviewFrames:
    def __init__(self, budget=192 * 1024**2):
        self.budget = budget
        self.reserved = 0
        self.clear()

    def clear(self):
        self.items = OrderedDict()
        self.bytes = 0

    def get(self, frame):
        packet = self.items.get(frame)
        if packet is not None: self.items.move_to_end(frame)
        return packet

    def _trim(self, protected=()):
        protected = set(protected)
        while self.items and self.bytes + self.reserved > self.budget:
            frame = next((i for i in self.items if i not in protected), next(iter(self.items)))
            self.bytes -= len(self.items.pop(frame)[1])

    def reserve(self, size, protected=()):
        self.reserved += size
        self._trim(protected)

    def release(self, size):
        self.reserved = max(0, self.reserved - size)

    def put(self, frame, packet):
        size = len(packet[1])
        if size + self.reserved > self.budget: return
        if frame in self.items: self.bytes -= len(self.items.pop(frame)[1])
        self.items[frame] = packet; self.bytes += size
        self._trim((frame,))

    def retain(self, predicate):
        for frame in list(self.items):
            if not predicate(frame): self.bytes -= len(self.items.pop(frame)[1])

    def complete(self, count):
        return len(self.items) == count and all(i in self.items for i in range(count))

    def ranges(self):
        ranges = []
        for frame in sorted(self.items):
            if ranges and frame == ranges[-1][1]: ranges[-1] = (ranges[-1][0], frame + 1)
            else: ranges.append((frame, frame + 1))
        return ranges


@dataclass(frozen=True)
class PreviewScope:
    intervals: tuple
    occurrences: int = 0

    @property
    def count(self):
        return sum(end - start for start, end in self.intervals)

    def contains(self, frame):
        return any(start <= frame < end for start, end in self.intervals)

    def position(self, frame):
        rank = 0
        for start, end in self.intervals:
            if start <= frame < end: return rank + frame - start
            rank += end - start
        return 0

    def frame_at(self, position):
        if not self.count: return 0
        position = max(0, min(self.count - 1, int(position)))
        for start, end in self.intervals:
            if position < end - start: return start + position
            position -= end - start
        return self.intervals[-1][1] - 1

    def step(self, frame, delta):
        return self.frame_at(self.position(frame) + delta)


def resolve_scope(composition, selected_ids, maximum, selected=False):
    if not selected or composition is None:
        return PreviewScope(((0, maximum + 1),))
    from synth_composition import section_placements
    fps = composition['fps']
    intervals = tuple((round(start * fps), round(end * fps))
                      for index, start, end, _repeat in section_placements(composition)
                      if composition['sections'][index]['id'] in selected_ids)
    return PreviewScope(intervals, len(intervals))


class PreviewScheduler:
    """Plan one stable bounded window, then deliver at most four frames per job."""
    batch_size = 4

    def plan(self, scope, current, fps, size, budget, explicit=False):
        frame_bytes = size[0] * size[1] * 3
        capacity = max(0, budget // frame_bytes)
        limited = scope.count > capacity
        if not capacity or not scope.count: return (), limited
        origin = scope.position(current)
        if explicit and not limited:
            ranks = tuple(range(origin, scope.count)) + tuple(range(origin))
        else:
            count = min(scope.count, capacity, math.ceil(fps * 2.5) + 1)
            behind = min(round(fps * .5), origin, max(0, count - 1))
            first = max(0, min(origin - behind, scope.count - count))
            last = first + count
            ranks = tuple(range(origin, last)) + tuple(range(origin - 1, first - 1, -1))
        return tuple(scope.frame_at(rank) for rank in ranks), limited

    def batch(self, target, cache):
        return tuple(frame for frame in target if frame not in cache.items)[:self.batch_size]
