# Sound, listening and export

[Documentation](README.md) · [Live MIDI](../LIVE_MIDI.md)

Nebula can play an imported soundtrack, keep a video's original audio on export,
or synthesize sound from supported visual motion. These are alternative output
routes. It does not mix a soundtrack, footage and generated sound together.
Montage has a narrower route: its own soundtrack or silence.

## Listen, apply, save and export

Open **Generate sound…** beside Soundtrack in the timeline toolbar. Once a sound
is attached, the button reads **Generated sound…**. It is available for Pleated
field and Chromatic lattice compositions. The window title is **Generate sound**.

| Action or state | What it means |
| --- | --- |
| **Listen**, with **Live audition** on | Plays the video transport and auditions current sound controls for Layered resonant synth or Color waves. You may be hearing an unapplied draft. |
| **Sound: Not applied** | Sound changes exist only in the editor. They have not replaced the project's sound. |
| **Apply sound** | Makes the draft the project's sound in one undoable edit. It does not write a file. |
| **Save project** / Command-S | Writes the editable project. If sound is pending, you choose Apply sound, Use applied sound or Cancel. |
| **File: Saved** | The applied project matches its saved file. An unapplied sound draft can still exist alongside it. |
| **Export MP4** | Renders applied project settings after resolving pending drafts. It does not save the project or record a live performance from the DAW. |

Read **Preview:** or **Listening:** to see the route currently heard. With Live
audition off, another output selected, or an original instrument, listening uses
the applied route until you apply the change. Original Electric / tape and Acid
triangle instruments prepare a waveform after **Apply sound**; **Prepare again**
retries preparation when needed.

When saving or exporting, **Use applied sound** keeps the sound draft in the
editor while using the already applied settings. On close or navigation away,
**Discard sound changes** discards that sound draft. **Keep editing** cancels
leaving. Changes made in **Visuals** apply to the project immediately and survive
discarding sound. The header names the document or Montage block being edited.

**Mute monitor** and **Listen level** change listening only. Instrument Level,
Mixer levels, EQ, Mute and Solo are authored settings: apply and save them to
keep them, and they affect generated export. Mixer Mute takes priority over
Solo. Monitor controls are disabled when they do not apply to the current route;
MIDI instruments and levels are managed in the DAW.

For export, set **Audio output** to **Generated sound**, **Existing soundtrack /
footage**, or **Silent**, then apply. Existing audio follows the Soundtrack export
choice when one is attached, otherwise the footage settings. Imported audio
responses can keep driving visuals even when a different audible output is chosen.

## Pleated field: drone and melody

Load **Pleated signal / acid motion**, then open **Generated sound…**. Its
**Layered resonant synth** follows the field's internal expansion, movement and
visible presence. It does not analyze the completed image or arbitrary footage.

- **Sound** controls the sustained base pitch, density, drive, stereo width,
  level and filter. **Opening** is a manual filter bias; visual movement adds
  to it. Disable the movement/filter connection for a fixed setting.
- **Oscillators** has three slots with waveform, level, semitone and fine tuning.
  Unison and Detune spread the enabled oscillators.
- **Arpeggio** has an independent root. Free Hz retains fractional tuning;
  Notes selects chromatic pitches. The original visual arpeggio starts short
  phrases from gestures; Notes chooses the pitch palette and Steps its length.
- **Motion** controls visual connections. **Continuity** softens the drop in
  level when a small part of the object remains visible; an absent source still
  fades to silence.
- **Mixer** balances Drone and Arpeggio, each with level, Mute, Solo and low/mid/high
  EQ. Both feed the shared drive and filter, so that filter can still remove
  highs boosted in a channel's EQ.

### Edit a step sequence

In **Arpeggio**, change **Arpeggio mode** to **Step sequencer**. All 16 steps stay
visible, grouped in fours. **Length** selects 1–16 active positions; shortening
it retains the other values for later reuse.

Select a step and edit Note, Velocity and Gate below the grid, or drag its pitch
and level lanes. Note is a semitone offset from Arpeggio root. Gate is the note's
length within its time slot; **Articulation** holds the separate Attack and
Release controls. A resting step retains its settings. Playback highlights the
current step without moving your editing selection.

Use arrows to move selection, Enter to edit the note, Escape to cancel numeric
input, and Space on a step to toggle its rest. **Focus pattern** temporarily hides
the video panel. These navigation actions do not change the sound.

**Tempo** (30–240 BPM) and **Division** set the sound rhythm, not video speed.
**Start → Visual gestures** plays a pattern at the next grid boundary after a
visual gesture and lets it finish before retriggering. **Loop with timeline**
repeats from time zero. The visual presence and filter connections still shape
the internal audio; a running pattern can be silent while its source is absent.

## Chromatic lattice: color-wave voices

Load **Lattice / chromatic pulse** and choose **Generate sound…**. **Color waves /
dual synth** maps the first two color transitions to ascending **Opening** and
**Color steps** notes. The return transition is unvoiced. Each voice has its own
root, scale, pitch range, decay, trigger point and timbre controls.

**Object → Motion & timing → Color timing** chooses Free optical or Musical
phrase. Free optical follows the changing color field. Musical phrase exposes
Tempo and Phrase length in 4/4 bars; at global speed 1, 96 BPM and two bars give
a five-second visual/audio phrase. This changes the visual source's timing too.
It is separate from the Pleated step sequencer.

The sound editor offers:

| Controls | Use |
| --- | --- |
| **Sound → Opening / Color steps → Engine** | Choose Original partials / FM, Analog ensemble or Chimes. Roots and visual triggers remain independent of timbre. |
| **Note clarity / Sustain voices** | Strengthen pitch clarity or limit overlapping ringing notes. Unlimited keeps all tails. |
| **Pad & space** | Enable a sustained root/chord, choose root-following or independent tuning, and set harmony, chorus, reverb and note delay. The pad stays out of note delay. |
| **Chimes** | Enable a separate resonant layer with its own tuning, triggers, decay, overlap and sends. This is distinct from choosing Chimes as an existing voice's engine. |
| **Resonance tuning** | Choose Metallic or Harmonic for chime voices; Harmonic aligns upper modes to harmonics of the root. |
| **Choir** | Add sustained OO/AH-like voices following the pad's root and harmony with an independent octave offset. |
| **Sub bass** | Add a centered lower root with adjustable harmonics and low-pass filtering. It stays outside shared chorus, reverb and delay. |
| **Motion → Wave sine** | Enable a continuous pitch following the radial position of enlarged cells; set low/high pitch and glide. |
| **Mixer** | Balance and mute/solo the enabled layers, with separate EQ. Chimes also has a bypassable high-pass filter. |

Optional layers must be enabled to hear them. Local variations described in old
release notes, such as Velvet Wave or Analog Sky, are personal documents; those
names are not additional built-in studies in this checkout.

## Looping and live changes

**Seamless audio loop** carries note releases and processing state across the
full timeline boundary. It does not make arbitrary visuals loop seamlessly. Use
a whole number of patterns for an even rhythm: 16 sixteenth-note steps at 120 BPM
last two seconds. Sustained oscillators make a tiny tuning adjustment to fit
whole cycles; note pitches remain as authored.

Live knob changes are auditioned with short crossfades. **Apply sound** stores
the current settings, not a recording of the knob performance. Sound Undo/Redo
restores drafts; applying is also undoable in the project. Sound-only edits keep
prepared video. **Prepare all video frames** caches the current composition at
its chosen preview resolution without starting playback. Source, effect or
resolution changes may require new frames.

To record visual gestures, use [Perform / Visuals](visual-performance.md).
To hear DAW instruments, follow [Live MIDI](../LIVE_MIDI.md). The
[versioned sound implementation record](visual-sound-prototype.md) explains DSP
and earlier instruments; its old UI instructions are historical.

## Import a soundtrack and make visuals react

Choose **+ Soundtrack…** or **File → Soundtrack…**, then **Import…** a local audio
file. Click its waveform to seek; double-click to reopen settings.

**In / Out** trim the audio and **Start** places it on the project timeline.
Choose **Silence at end** or **Loop trimmed audio**, then **Apply**. Visual clips
determine total duration. Moving or repeating clips does not restart the absolute
soundtrack clock. **Output volume** is saved; **Preview monitor** volume and Mute
only affect listening. Preview can monitor the soundtrack even when its
**Export audio** choice is footage or silence.

**Replace…** selects another track and resets its trim while keeping placement
and output choices. **Relink…** repairs moved/changed media and keeps trim; the
replacement must cover Out. Ordinary Save references the media; Save as study
copies it. Native preview seeks are approximate and trimmed preview loops may
have a small gap. Export assembles timing on the audio sample clock.

Open **React to audio… → Add response**, choose an active visual control and a
Bass/Mids/Highs/Full band or custom Hz range. Set Amount, Sensitivity, Rise and
Fall, then **Apply**. Several responses to the same control add before clamping.
Bypass or zero Amount restores the authored look. A response does not enable
its target effect. Monitor mute and the audible export route do not disable
analysis. Missing active audio must be relinked.

There is one soundtrack and up to 16 band-energy responses. These measure energy,
not isolated instruments, beat detection or onset-triggered word advancement.
Targets include Radial bloom, Bloom, Raster grain, drift, tape, jitter, color
separation and Signal repetition. The built-in **Radial / chromatic bloom** is
silent until you supply audio; the historical audio-bloom demos require their
owner's local media.

## Audio in Montage

A block can retain generated sound and audio-response settings while you edit
it. Exporting from that block exports the parent Montage. The Montage exporter
uses the parent soundtrack or silence and does not mix generated sound or
footage audio from its blocks. Check **Details** before export. See
[Montage](native-montage.md) for block editing, timing drafts and media handling.
