"""Separate A/B packets within one bounded preview memory budget."""
from collections import OrderedDict
from synth_preview import PreviewFrames


class ComparisonFrames(PreviewFrames):
    def clear(self):
        super().clear()
        self.banks = {}; self.namespace = None; self.anchors = {}

    def switch(self, namespace):
        if namespace == self.namespace: return
        self.banks[self.namespace] = self.items
        self.namespace = namespace
        self.items = self.banks.setdefault(namespace, OrderedDict())

    def anchor(self, frame):
        self.anchors[self.namespace] = frame

    def _trim(self, protected=()):
        # Evict an inactive branch first, keeping its last viewed frame when
        # possible. Reservations from cancelled workers share this same budget.
        protected = set(protected)
        while self.bytes + self.reserved > self.budget:
            candidates = [(key, bank) for key, bank in self.banks.items() if key != self.namespace and bank]
            candidates.append((self.namespace, self.items))
            victim = None
            for key, bank in candidates:
                avoid = protected if key == self.namespace else {self.anchors.get(key)}
                frame = next((frame for frame in bank if frame not in avoid), None)
                if frame is not None: victim = (bank, frame); break
            if victim is None:
                victim = next(((bank, next(iter(bank))) for _, bank in candidates if bank), None)
            if victim is None: break
            bank, frame = victim; self.bytes -= len(bank.pop(frame)[1])
