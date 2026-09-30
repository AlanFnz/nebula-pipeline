"""Bounded, generation-scoped preview frames. Never used for final export."""
from collections import OrderedDict


class PreviewFrames:
    def __init__(self, budget=192 * 1024**2):
        self.budget = budget
        self.clear()

    def clear(self):
        self.items = OrderedDict()
        self.bytes = 0

    def get(self, frame):
        packet = self.items.get(frame)
        if packet is not None: self.items.move_to_end(frame)
        return packet

    def put(self, frame, packet):
        size = len(packet[1])
        if size > self.budget: return
        if frame in self.items: self.bytes -= len(self.items.pop(frame)[1])
        self.items[frame] = packet; self.bytes += size
        while self.bytes > self.budget:
            self.bytes -= len(self.items.popitem(last=False)[1][1])

    def complete(self, count):
        return len(self.items) == count and all(i in self.items for i in range(count))
