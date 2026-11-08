from integrations.ableton.Nebula_Visuals.watch import InstrumentWatcher, REFRESH_PREFIX, channel_for
from synth_live_midi import REFRESH_PREFIX as ENGINE_PREFIX


class Device:
    def __init__(self, kind=1, chains=None):
        self.type = kind; self.is_active = True
        self.can_have_chains = chains is not None; self.chains = chains


class Track:
    def __init__(self, devices, channel=4, port='Nebula Visuals'):
        self.devices = devices; self.has_midi_input = True
        self.input_routing_type = {'display_name': port}
        self.input_routing_channel = {'display_name': 'Ch. %d' % channel}


def test_new_instrument_restores_once_and_fx_or_rename_do_not_retrigger():
    instrument = Device(); t = Track([instrument]); w = InstrumentWatcher()
    assert w.update([t], 0) == []
    assert w.update([t], .41) == [3]
    assert w.update([t], 1) == []
    t.devices.append(Device(2)); instrument.name = 'Renamed'
    assert w.update([t], 2) == []
    t.devices[0] = Device()  # Same type, different instance.
    assert w.update([t], 3) == []
    assert w.update([t], 3.41) == [3]
    assert w.update([t], 20) == []


def test_removal_load_debounce_and_nested_rack():
    chain = Track([Device()]); t = Track([Device(chains=[chain])])
    w = InstrumentWatcher(); w.update([t], 0); w.update([t], 1)
    chain.devices = []; assert w.update([t], 2) == []
    assert w.update([t], 3) == []
    chain.devices = [Device()]; assert w.update([t], 4) == []
    chain.devices = [Device()]; assert w.update([t], 4.3) == []
    assert w.update([t], 4.5) == []
    assert w.update([t], 4.71) == [3]
    w.update([], 5); assert not w.states


def test_only_explicit_nebula_channels_and_no_other_tracks():
    assert REFRESH_PREFIX == ENGINE_PREFIX
    tracks = [Track([Device()], port='All Ins'), Track([Device()], channel=8)]
    all_channels = Track([Device()]); all_channels.input_routing_channel['display_name'] = 'All Channels'
    tracks.append(all_channels)
    w = InstrumentWatcher()
    assert w.update(tracks, 0) == w.update(tracks, 1) == []
    assert all(channel_for(t) is None for t in tracks)


def test_bypass_then_enable_recovers_without_poll_retrigger():
    d = Device(); t = Track([d]); w = InstrumentWatcher()
    w.update([t], 0); assert w.update([t], 1) == [3]
    d.is_active = False; w.update([t], 2); assert w.update([t], 3) == []
    d.is_active = True; w.update([t], 4); assert w.update([t], 5) == [3]
    assert w.update([t], 6) == []
