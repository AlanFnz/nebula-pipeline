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
