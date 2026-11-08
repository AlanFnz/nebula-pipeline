"""Read-only instrument identity tracking, independent of Live imports."""
import re

REFRESH_PREFIX = (0xF0, 0x7D, 0x4E, 0x42, 0x4C, 1, 1)


def display_name(route):
    return route.get('display_name', '') if isinstance(route, dict) else route.display_name


def channel_for(track):
    if not track.has_midi_input or display_name(track.input_routing_type) != 'Nebula Visuals':
        return None
    match = re.search(r'(\d+)$', display_name(track.input_routing_channel))
    if match and 1 <= int(match.group(1)) <= 7:
        return int(match.group(1)) - 1
    return None  # All Channels is ambiguous; never retrigger unrelated layers.


def instruments(devices):
    result = []
    for device in devices:
        if int(device.type) != 1:
            continue
        if device.can_have_chains:
            for chain in device.chains:
                result.extend(instruments(chain.devices))
        else:
            result.append((device, device.is_active))
    return tuple(result)


class InstrumentWatcher:
    def __init__(self, settle=.4):
        self.settle = settle
        self.states = {}

    def update(self, tracks, now):
        """One refresh per changed channel, after loading settles. No periodic notes."""
        present = set(); refresh = set()
        for track in tracks:
            try:
                channel = channel_for(track)
                if channel is None:
                    continue
                present.add(track)
                fingerprint = (channel, instruments(track.devices))
                state = self.states.get(track)
                if state is None or state[0] != fingerprint:
                    self.states[track] = (fingerprint, now, True)
                elif state[2] and now - state[1] >= self.settle:
                    self.states[track] = (fingerprint, state[1], False)
                    if any(active for _, active in fingerprint[1]):
                        refresh.add(channel)
            except (RuntimeError, ReferenceError):
                # A device may disappear between enumerating and reading it.
                self.states.pop(track, None)
        for track in set(self.states) - present:
            del self.states[track]
        return sorted(refresh)
