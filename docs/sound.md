# Sound

[Documentation](README.md) · [Live MIDI](../LIVE_MIDI.md)

A composition can export generated sound, existing soundtrack/footage audio, or
silence. These routes do not mix together. Choose **Audio output** in the sound
editor and apply it. Montage uses its own soundtrack or silence.

## Listen, apply, save and export

Open **Synthesizer** beside Soundtrack. It is available for Pleated field and
Chromatic lattice.

For Ableton instruments, select **Audio output → Ableton Live (MIDI)**, then
**Apply MIDI** and **Save composition**. The toolbar becomes **Live controls** and
Play uses MIDI even with that editor closed. Internal settings remain available
when switching back. See [Live MIDI](../LIVE_MIDI.md) for routing and export.

| Action | Result |
| --- | --- |
| Listen, with Live audition on | Hear the current Layered synth or Color waves draft. |
| Apply sound | Put the draft in the project as an undoable edit. |
| Save composition / Save montage | Write the complete owning document to disk. |
| Export MP4 | Render the applied settings, after resolving pending drafts. |

**File: Saved** can coexist with an unapplied sound draft. On save or export,
**Use applied sound** uses the project's settings and keeps the draft for later.
On leaving, **Discard sound changes** drops it. Visuals edits already belong to
the project and survive discarding sound.

Read **Preview:** or **Listening:** to check what you hear. With Live audition
off or another output selected, playback uses the applied route. The original
Electric / tape and Acid triangle instruments prepare audio after Apply sound.
The header names the same document or Montage block as the visual inspector.
Inside a block, sound and Visuals affect its internal composition; Save montage
writes the complete Montage. This does not change Montage's audio export route.

**Listen level** and **Mute monitor** affect listening only. Instrument and Mixer
levels, EQ, Mute and Solo affect generated export when applied. Mute wins over
Solo. Live MIDI sends notes to DAW instruments; their audio must be recorded or
exported separately.

## Pleated field: drone and melody

Load **Pleated signal / acid motion** for **Layered resonant synth**. Sound and
Oscillators shape the drone; Arpeggio has its own root. Motion connects visual
movement to the sound, and Mixer balances Drone and Arpeggio.

### Edit a step sequence

In Arpeggio, choose **Arpeggio mode → Step sequencer**. Length selects up to 16
steps. Select a step to edit Note, Velocity and Gate; Space toggles its rest.
Gate sets note length; Attack and Release shape the envelope.

Tempo and Division set rhythm. **Start → Visual gestures** triggers a pattern
from movement; **Loop with timeline** repeats from time zero. These controls do
not change video speed. Visual presence and filter connections can still make
a running pattern quiet or silent.

## Chromatic lattice: color-wave voices

Load **Lattice / chromatic pulse** and open Synthesizer. **Color waves / dual
synth** maps color transitions to Opening and Color steps notes. Each has its own
root, scale and engine. Enable Pad, Chimes, Choir, Sub bass or Wave sine for
additional layers, then balance them in Mixer.

**Object → Motion & timing → Color timing → Musical phrase** ties the visual
cycle to Tempo and Phrase length. Free optical keeps independent visual clocks.

## Looping and live changes

**Seamless audio loop** carries sound across the timeline boundary; it does not
make the visuals loop. Apply sound stores settings, not a knob performance.
Use [Perform / Visuals](visual-performance.md) to record visual gestures.

## Import a soundtrack and make visuals react

Choose **+ Soundtrack → Import…**. Set In/Out, Start and the end behavior, then
Apply. The visual timeline determines the piece's duration. **Relink…** repairs
moved media while keeping trim; ordinary Save does not copy the audio file.

**React to audio… → Add response** maps a frequency band to an active visual
control. Set Amount, Sensitivity, Rise and Fall, then Apply. Up to 16 responses
can follow band energy; this does not isolate instruments or detect beats.
Monitor mute and the chosen export route do not disable these responses.

## Audio in Montage

You can hear a supported block's sound while editing it. Export from that editor
still exports the parent Montage, using its soundtrack or silence. It does not
mix generated sound or original footage audio from blocks. Check Details before
exporting. See [Montage](native-montage.md).
