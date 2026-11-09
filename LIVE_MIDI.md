# Live MIDI

[Sound](docs/sound.md) · [Documentation](docs/README.md)

Nebula can play DAW instruments from **Layered resonant synth** (Pleated) or
**Color waves / dual synth** (Chromatic lattice). This experimental route is off
by default and is not saved in projects. The virtual-port workflow has been tried
on macOS; other platforms are unverified.

## Connect

1. Open **Synthesizer**, enable sound and select
   **Audio output → Generated sound**.
2. Enable **Send live MIDI to Ableton / DAW (experimental)**. The **Nebula
   Visuals** MIDI source appears; macOS needs no IAC setup.
3. In Live's MIDI settings, enable Track input for Nebula Visuals. Add an
   instrument track, select that input and an explicit channel below, then set
   monitoring to **In**. Use the equivalent routing in another DAW.
4. Press **Listen** or Play in Nebula. Live's transport need not run.

| Channel | Color waves | Layered resonant synth |
| --- | --- | --- |
| 1 | Opening | Drone |
| 2 | Color steps | Arpeggio / Step sequencer |
| 3 | Pad chord | Unused |
| 4 | Choir chord | Unused |
| 5 | Chimes | Unused |
| 6 | Sub bass | Unused |
| 7 | Wave sine | Unused |

Set the receiving instrument's pitch-bend range to **±2 semitones**; Color waves
channel 7 needs **±24**. Nebula sends range requests, but some instruments require
manual setup. Fractional tuning uses pitch bend.

## Open the study's Live Set

Choose **Link Live Set…** beside the MIDI controls and select an existing `.als`.
Save the project or use **Save as study…** to keep the association. The button
then shows the Set's name; click **Open in Live** to open it. Its menu lets you
change or remove the link. If the file moved, Open asks for its new location.

The Set stays in its original folder and is not copied into the study. Opening
it does not change Nebula's MIDI or playback settings. Save changes to the Set
in Live.

## While playing

**Refresh MIDI notes** restores held notes after connecting or changing an
instrument. It restarts their envelopes without moving the video. **Stop MIDI
notes** stops playback and sends all-notes/sound-off. Pause releases notes;
seeking restores them. Seamless loops retain held chords across the boundary.

Nebula supplies pitch, note timing, velocity and layer Mute/Solo. Choose sounds,
effects and mix levels in Live. CC 1 carries expansion; CC 74 carries motion for
Color waves and filter opening for Pleated. Pleated also sends presence on CC 11.
Map these controls in the receiving instrument if you want it to respond.

There is no MIDI Clock, Ableton Link or DAW transport sync. Recording may need
start alignment; DAW buffers and instruments affect latency.

## Save and export

Apply sound and Save project retain Nebula's sound settings. MIDI monitoring
sends no audio back to Nebula: MP4 export uses the applied internal audio route.
Record or export Live's audio separately. Internal filters, ambience and Mixer
levels do not become equivalent processing in Live.

## Optional Ableton instrument recovery

The [Ableton companion](integrations/ableton/README.md) can restore held notes
automatically when an instrument is replaced or activated. It is optional;
manual Refresh works without installing it. Preset changes inside an unchanged
plug-in may still need a manual refresh.
