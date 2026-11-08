# Nebula Visuals companion for Ableton

This optional Remote Script supports the [live MIDI pilot](../../LIVE_MIDI.md).
Follow that guide for installation and instrument/channel routing. The installer
copies `__init__.py`, `surface.py` and `watch.py` into the chosen User Library;
it does not install Nebula, instruments or a Live Set.

`watch.py` detects device identity/activation changes on tracks receiving explicit
Nebula Visuals channels. `surface.py` sends a private, non-commercial SysEx
request through **Nebula Control** after the replacement settles. Nebula restores
currently held notes and tuning for the requested channel while playing.

The shared prefix is `F0 7D 4E 42 4C 01 01`, followed by the zero-based channel
and `F7`. It requests note restoration, not transport or project changes.
Nebula's implementation is [synth_live_midi.py](../../synth_live_midi.py).
The receiver remains responsible for its instrument state and envelope release.

Tests in [test_ableton_midi_recovery.py](../../tests/test_ableton_midi_recovery.py)
use fake tracks/devices and cover replacement, bypass/re-enable, nested racks,
explicit-channel filtering and no repeated restoration. MIDI engine tests use
fake output ports. These do not replace a manual check with a particular Live
version and plug-in. The recorded 12.4.6 check is in the
[sound implementation history](../../docs/visual-sound-prototype.md#live-midi-validation).
