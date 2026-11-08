# Nebula Visuals companion for Ableton

Optional companion for [Live MIDI](../../LIVE_MIDI.md). It watches instrument
replacement/activation and restores held notes on the affected channel. It does
not edit the Set or periodically retrigger chords.

## Install and connect

From a prepared repository, select Live's actual, existing User Library:

```sh
.venv/bin/python scripts/install_ableton_bridge.py "/path/to/Ableton/User Library"
```

The installer copies `__init__.py`, `surface.py` and `watch.py` into
`Remote Scripts/Nebula_Visuals`. Save your Live work and restart when convenient.
Enable MIDI in Nebula, then choose an unused Control Surface slot in Live:
**Nebula_Visuals**, **Input: None**, **Output: Nebula Control**.

Instrument tracks still receive **Nebula Visuals**, with explicit channels and
monitoring In. Do not assign that note input to the control surface. A preset
change inside the same plug-in may need manual **Refresh MIDI notes**.

## Protocol and checks

`watch.py` detects device changes; `surface.py` sends a private SysEx request
through Nebula Control once the replacement settles. The prefix is
`F0 7D 4E 42 4C 01 01`, followed by the zero-based channel and `F7`.
[synth_live_midi.py](../../synth_live_midi.py) restores held notes and tuning while
playing. Requests while paused do nothing.

[Companion tests](../../tests/test_ableton_midi_recovery.py) use fake tracks and
devices; MIDI engine tests use fake ports. Earlier checks with Live 12.4.6 are
in the [implementation record](../../docs/visual-sound-prototype.md#live-midi-validation).
They do not guarantee a particular plug-in's behavior or latency.
