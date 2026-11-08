# Live MIDI pilot

Color waves can drive a DAW while Nebula plays its video. In Generate sound,
turn on **Send live MIDI to Ableton / DAW (experimental)** and press Listen or
Play. The virtual source is **Nebula Visuals**; no IAC setup is required on macOS.
Use MIDI input Track on, monitoring In, and one receiving instrument per channel.
The receiver can be opened before or after the port appears.

| Channel | Layer |
| --- | --- |
| 1 | Opening |
| 2 | Color steps |
| 3 | Pad chord |
| 4 | Choir chord |
| 5 | Chimes |
| 6 | Sub bass |
| 7 | Radial sine |

Notes derive from the same visual signals, scales and articulation as internal
synthesis. Velocity, note on/off and fractional tuning are transmitted. Set
receiving pitch-bend ranges to ±2 semitones, except channel 7 (±24). RPN pitch
range is sent too, but instruments may require manual range configuration.
CC 1 carries expansion and CC 74 motion, scaled to 0–127 at up to 50 Hz. These
are optional modulation sources; map them explicitly in the receiving DAW.

Nebula is the timing source: the DAW receives already-timed notes and does not
need its transport running to produce audio. This pilot does **not** transmit
MIDI Clock, Song Position, Ableton Link or DAW transport commands. Recording
into a beat grid may require aligning its start. There is no automatic latency
calibration; the DAW's audio-buffer latency remains relevant.

Pause releases voices; seek restores active notes. Seamless loops keep sustained
chords playing. **Stop MIDI notes** stops playback and sends all-notes/sound-off.
Closing the document or switching back to internal sound releases the port.

**Refresh MIDI notes** re-sends held notes at the current video position,
without pause/play. Use it after changing a preset inside a plug-in or connecting
a receiver while already playing. It restarts those instruments' envelopes.

## Instrument replacement recovery (Ableton, optional)

Install the companion once, with Live's actual User Library directory:

```sh
python scripts/install_ableton_bridge.py "/path/to/Ableton/User Library"
```

Restart Live, turn on Nebula's MIDI route, then in Live MIDI settings choose an
unused Control Surface slot: **Nebula_Visuals**, **Input: None**,
**Output: Nebula Control**. Keep the seven instrument tracks receiving
**Nebula Visuals**, explicit channels 1–7, monitoring In. Never assign that note
input to the control surface. Other control surfaces and MIDI ports can stay as
they are. This follows [Live's remote-script installation workflow](https://help.ableton.com/hc/en-us/articles/209072009-Installing-third-party-remote-scripts).

The companion observes instrument identity/activation without editing the Set.
After a replacement settles, it sends one private SysEx request to Nebula, which
restores just that channel's currently held notes and tuning. It does not reset
the video, retrigger other layers, or periodically pulse sustained chords. When
paused, requests do nothing. Switching presets *inside* an unchanged plug-in
may not be observable: use Refresh MIDI notes in that case.

## Sustained notes and DAW envelopes

Pad and Choir hold their chords throughout playback, including loop boundaries.
A receiving preset can still fade out while holding a key. In Podolski, use a
nonzero Sustain and **Fall-Rise: 0** for a continuous level: negative Fall-Rise
values decay to silence even before note-off, as described in the
[Podolski guide](https://u-he.com/downloads/manuals/plugins/podolski/Podolski-user-guide.pdf).
After changing an envelope on an already-silent voice, refresh the MIDI notes.
CC 1/74 may also affect existing preset mappings; inspect the plug-in's modulation
routing when debugging an unexpected fade.

Opening/Steps/Chimes are finite notes. Their MIDI gate is limited by the voice's
Decay setting and visual polyphony gate; long gaps between phrases do not hold
the last note open. Any release tail after note-off belongs to the DAW instrument.

Pitch, scales, note activity and layer mute/solo come from Nebula. Instruments,
filter/envelope timbre, EQ, sends, level and mix are adjusted in the DAW. MIDI
cannot reproduce the internal synthesizer's sound automatically. The native
Ableton pilot is a timbral approximation, not a sample-identical conversion.

This is a monitoring option, off by default and not serialized into studies.
Existing studies/rendering stay unchanged. Export MP4 still uses the saved
Nebula sound; record/export the DAW separately for this experiment.

## Verification

- Unit coverage: original attacks/tuning; sustain through seek and wrap; mute,
  solo and disabled layers; thread start/stop/seek/close; session-only UI state.
- Local CoreMIDI loopback over two 20-second cycles: all 328 expected authored
  attacks arrived, maximum scheduling offset 3.3 ms in that run. Pad and choir
  each attacked once (five tones each), with no loop retrigger. This measures
  MIDI delivery, not end-to-end audio latency.
- Ableton Live 12.4.6 Suite: seven native instrument tracks received their
  separate channels. Actual resampled audio was captured; no clipped samples.

- 0.83.1 installed-app QA with Live 12.4.6 and the user’s Podolski set:
  re-enable and remove/Undo reloaded Choir without pause/play. CoreMIDI
  capture over 51.8 seconds showed exactly one five-note Choir restoration,
  no Pad note on/off events, and no additional Choir releases through the
  following loop. Live’s Choir meter remained active. Final Color Steps gate
  was approximately 0.68 seconds, matching the authored decay.
