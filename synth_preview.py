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


# Cache validity is independent of the generation used to reject worker results.
# A conservative classifier can retain pixels while the generation still changes.
from bisect import bisect_right
import copy
import hashlib
import json
from pathlib import Path


def _file_fingerprint(path):
    path = Path(path).expanduser().resolve()
    try:
        stat = path.stat()
        return (str(path), stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
    except OSError:
        return (str(path), 'unavailable')


def preview_context(sequence, size, bypass, proxy_root=None):
    """Actual source/proxy identity, dimensions and source-only renderer inputs."""
    media = ()
    if sequence and 'footage' in sequence:
        from synth_video import PROXY_EDGE, proxy_directory
        from synth_section_sources import rendered_footage
        sources = []
        for footage in rendered_footage(sequence):
            key = hashlib.sha256(json.dumps([footage['path'], footage['identity'], footage['sample_fps'], PROXY_EDGE, 1], sort_keys=True).encode()).hexdigest()
            proxy = (Path(proxy_root) if proxy_root else proxy_directory()) / (key + '.mkv')
            identity = (_file_fingerprint(footage['path']), _file_fingerprint(proxy))
            if identity not in sources: sources.append(identity)
        media = tuple(sources)
    return (tuple(size), bool(bypass), media)


@dataclass(frozen=True)
class RenderValidity:
    identity: object
    composition: object
    sequence: object
    preset: object
    context: tuple

    @classmethod
    def capture(cls, identity, composition, sequence, preset, context):
        return cls(identity, copy.deepcopy(composition), copy.deepcopy(sequence),
                   copy.deepcopy(preset) if sequence is None else None, context)


def retained_frame_predicate(previous, current):
    """Return None for full-clear; otherwise decide each absolute cached frame.

    Only section visual edits with identical compiled clocks/cues/global inputs
    qualify. Dependencies are derived from compiled cues, including each repeat
    and the previous state consumed by a transition into a neighboring section.
    """
    if previous is None or previous.identity is not current.identity or previous.context != current.context:
        return None
    if previous.sequence == current.sequence and previous.preset == current.preset and previous.composition == current.composition:
        return lambda _frame: True
    before, after = previous.composition, current.composition
    old, new = previous.sequence, current.sequence
    if before is None or after is None or old is None or new is None: return None
    if {k: v for k, v in before.items() if k != 'sections'} != {k: v for k, v in after.items() if k != 'sections'}:
        return None
    visual = {'effects', 'geometry', 'macros'}
    if len(before['sections']) != len(after['sections']): return None
    changed_sections = set()
    for first, second in zip(before['sections'], after['sections']):
        if {k: v for k, v in first.items() if k not in visual} != {k: v for k, v in second.items() if k not in visual}:
            return None
        if first != second: changed_sections.add(second['id'])
    if not changed_sections: return None
    if {k: v for k, v in old.items() if k != 'states'} != {k: v for k, v in new.items() if k != 'states'}:
        return None
    if old['states'].keys() != new['states'].keys(): return None
    changed_states = {key for key in new['states'] if old['states'][key] != new['states'][key]}
    if not changed_states or any(key.split(':', 1)[0] not in changed_sections for key in changed_states): return None
    clocks = {'seed', 'treatment_fps', 'export_fps', 'loop_seconds', 'variation_fps', 'variation_mode', 'animation'}
    for state in changed_states:
        first, second = old['states'][state], new['states'][state]
        if first.get('preset') != second.get('preset'): return None
        if any(first.get('overrides', {}).get(key) != second.get('overrides', {}).get(key) for key in clocks): return None
    cues = new['cues']; times = [cue['time'] for cue in cues]; fps = new['fps']

    def valid(frame):
        t = frame / fps
        index = max(0, bisect_right(times, t) - 1)
        cue = cues[index]
        if cue['state'] in changed_states: return False
        if index and cue.get('transition', 'cut') != 'cut' and t < cue['time'] + cue.get('duration', 0):
            if cues[index - 1]['state'] in changed_states: return False
        return True

    return valid
