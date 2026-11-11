"""Separate A/B packets within one bounded preview memory budget."""
from collections import OrderedDict
from synth_preview import PreviewFrames


class ComparisonFrames(PreviewFrames):
    def clear(self):
        for store in getattr(self, 'disk_banks', {}).values(): store.close()
        self.disk_banks = {}
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
        protected = protected if isinstance(protected, range) else set(protected)
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

    def enable_full(self, size, count):
        from synth_preview_disk import DiskFrames
        if self.namespace in self.disk_banks:
            self.disk_banks[self.namespace].check_capacity(count)
            return
        store = DiskFrames(size, max(count, len(self.items)))
        try:
            for frame, packet in self.items.items(): store.put(frame, packet)
        except Exception:
            store.close()
            raise
        self.disk_banks[self.namespace] = store

    def disable_full(self):
        store = self.disk_banks.pop(self.namespace, None)
        if store: store.close()

    def available(self):
        store = self.disk_banks.get(self.namespace)
        return set(self.items) | store.frames if store else super().available()

    def contains(self, frame):
        store = self.disk_banks.get(self.namespace)
        return frame in self.items or bool(store and frame in store.frames)

    def get(self, frame):
        packet = super().get(frame)
        store = self.disk_banks.get(self.namespace)
        if packet is None and store:
            packet = store.get(frame)
            if packet is not None: super().put(frame, packet)
        return packet

    def put(self, frame, packet):
        store = self.disk_banks.get(self.namespace)
        if store: store.put(frame, packet)
        super().put(frame, packet)

    def retain(self, predicate):
        super().retain(predicate)
        store = self.disk_banks.get(self.namespace)
        if store: store.retain(predicate)
