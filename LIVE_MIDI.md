# Live MIDI pilot

[Sound guide](docs/sound.md) · [Documentation](docs/README.md)

Nebula can send visual notes to a DAW from **Layered resonant synth** (Pleated)
or **Color waves / dual synth** (Chromatic lattice). This is an experimental
monitoring route, off by default and not stored in projects or studies. The
virtual-port workflow has been exercised on macOS; other platforms are unverified.

MIDI carries notes and controls, not audio. Choose instruments, envelopes,
effects and mix levels in the DAW. Nebula's MP4 export still renders its applied
internal sound or chosen audio route. Record or export the DAW audio separately.

## Connect a receiving instrument

1. Open a supported composition and **Generate sound…** (or **Generated sound…**).
   Enable sound and choose **Audio output → Generated sound**.
2. Turn on **Send live MIDI to Ableton / DAW (experimental)**. Nebula creates
   the virtual **Nebula Visuals** source; the macOS route needs no IAC setup.
3. In Ableton's MIDI settings, enable Track input for Nebula Visuals. Create an
   instrument track for each layer you want, select Nebula Visuals and that
   layer's explicit channel, and set monitoring to **In**. Another DAW needs the
   equivalent input, channel and monitoring setup.
4. Press **Listen** or Play in Nebula. Nebula supplies already-timed notes; the
   DAW transport need not run to hear them. Configure pitch-bend ranges below.

A receiver can connect before or after the port appears. **Refresh MIDI notes**
re-sends currently held notes without moving or pausing the video. Use it after
connecting during playback or changing a plug-in preset; it restarts envelopes.
**Stop MIDI notes** stops playback and sends all-notes/sound-off. Pause releases
voices; seeking restores active notes. With seamless looping, held chords stay
on across the boundary. Closing the document or leaving the MIDI route releases
the port.

Nebula sends no MIDI Clock, Song Position, Ableton Link or DAW transport commands.
Recording onto a beat grid may require aligning the start. There is no automatic
audio-latency calibration; the receiving DAW's buffer and instruments matter.

## Channels and controls

| Channel | Color waves | Layered resonant synth |
| --- | --- | --- |
| 1 | Opening | Drone |
| 2 | Color steps | Arpeggio / Step sequencer |
| 3 | Pad chord | Unused |
| 4 | Choir chord | Unused |
| 5 | Chimes | Unused |
| 6 | Sub bass | Unused |
| 7 | Wave sine | Unused |

Pitch, scales, attacks, velocity, enabled connections and layer Mute/Solo come
from Nebula. Set pitch-bend range to **±2 semitones**, except Color waves channel
7, which uses **±24**. Nebula also sends RPN range messages, but receiving
instruments may need manual configuration. Fractional root tuning uses pitch bend.

For Color waves, CC 1 carries expansion and CC 74 carries motion at up to 50 Hz.
Opening, Color steps and Chimes have finite gates capped by Decay and their
visual voice limits; a gap to the next phrase does not hold the last note.
Pad and Choir hold chords; the receiving envelope can still fade during a held
key. Check sustain and modulation settings if a voice unexpectedly disappears.

For Pleated, channels 1–2 receive CC 1 (smoothed expansion), CC 74 (normalized
filter opening, including manual Opening and note accents) and CC 11 (smoothed
visual presence with Continuity). Map CC 74 logarithmically between the internal
Closed/Open filter frequencies to approximate that sweep. Map CC 11 if you want
the DAW's loudness to follow presence. Unmapped controls cannot reproduce these
internal responses. Sequencer Gate sets MIDI note length; release belongs to
the receiving instrument.

Nebula's internal oscillator bank, filters, EQ, ambience and mixer levels do not
become equivalent DAW processing. CCs must be mapped deliberately, and an existing
preset may already assign them. Matching the notes does not guarantee matching
timbre or loudness.

## Optional Ableton instrument recovery

The companion watches instrument replacement/activation and asks Nebula to
restore only the affected channel's held notes. It does not edit the Set or
periodically retrigger sustained chords. Preset changes inside an unchanged
plug-in may be invisible to it; use Refresh MIDI notes manually then.

From a prepared repository, install it into Live's actual User Library:

```sh
.venv/bin/python scripts/install_ableton_bridge.py "/path/to/Ableton/User Library"
```

This copies three Python files into `Remote Scripts/Nebula_Visuals`. The directory
must already exist as a User Library. After saving your Live work, restart Live
when convenient, enable Nebula's MIDI route, and choose an unused Control Surface
slot: **Nebula_Visuals**, **Input: None**, **Output: Nebula Control**. Instrument
tracks continue receiving **Nebula Visuals**, with explicit channels from the
table and monitoring In. Do not assign the note input to the control surface.

Requests while paused do nothing. The companion does not change other control
surfaces or ports. See the [integration reference](integrations/ableton/README.md)
for its protocol and tests.

## Evidence and limits

Source and fake-port tests cover note/tuning plans, gates, mute/solo, seek,
looping, refresh, shutdown and the session-only UI state. Earlier local tests
with Ableton Live 12.4.6 are preserved in the
[implementation record](docs/visual-sound-prototype.md#live-midi-validation).
Those runs are not a latency guarantee or a current test of every plug-in.
