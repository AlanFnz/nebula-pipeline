# Live MIDI

[Sound](docs/sound.md) · [Documentation](docs/README.md)

Nebula can play DAW instruments from **Layered resonant synth** (Pleated) or
**Color waves / dual synth** (Chromatic lattice). **Ableton Live (MIDI)** is a
playback destination saved in projects and personal studies. Existing studies
keep their internal sound until you choose Live. The virtual-port workflow has
been tried on macOS; other platforms are unverified.

## Connect

1. Open **Synthesizer**, select **Audio output → Ableton Live (MIDI)** and
   enable MIDI. Choose **Apply MIDI**, then **Save project**.
2. The toolbar now shows **Live controls**. The **Nebula Visuals** MIDI source
   appears; macOS needs no IAC setup.
3. In Live's MIDI settings, enable Track input for Nebula Visuals. Add an
   instrument track, select that input and an explicit channel below, then set
   monitoring to **In**. Use the equivalent routing in another DAW.
4. Press **Listen** or Play in Nebula. Live's transport need not run.

Play keeps using MIDI after closing the editor and after reopening the project.
Loading a project does not launch Live: open its Set explicitly. A ready MIDI
port does not confirm that Live's tracks are receiving it. If MIDI fails,
Nebula stays silent; **Reconnect MIDI** retries without changing the destination.

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

Choose **Link Live Set** beside **Synthesizer** in the timeline toolbar and select
an existing `.als`. The same access is inside Synthesizer beside the MIDI controls.
Save the project or use **Save as study…** to keep the association. Click
**Open in Live** to open the linked Set. Its menu lets you
change or remove the link. If the file moved, Open asks for its new location.

Linked studies have an **Ableton Live** label in the study selector and library.
In **Browse**, use the Ableton Live filter or search for the Set's filename.

The Set stays in its original folder and is not copied into the study.
**Open in Live** also selects Live playback for supported instruments. The
button's menu offers **Use Ableton Live for playback** without opening a Set;
uncheck it to return to the internal synthesizer. These are undoable edits.
Save Nebula's project to retain the destination, and save instrument changes in Live.
Linking, changing or removing the `.als` association alone does not change playback.

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

**Apply MIDI** and **Save project** retain notes, visual mappings and the Live
destination. Live controls show musical settings and channel Mute/Solo; timbre,
levels and effects belong in Live. Internal synth settings remain stored for
returning to that mode.

MIDI sends no audio back to Nebula. In saved Live mode, MP4 export is silent
unless you import a recording as a soundtrack and select it for export. Check
the export summary. Nebula never substitutes its internal synth for Live audio.

The older **Send live MIDI… (experimental)** checkbox remains a temporary
monitoring option with internal output selected. It is not saved and does not
change exports. Use **Ableton Live (MIDI)** for a persistent destination.

## Optional Ableton instrument recovery

The [Ableton companion](integrations/ableton/README.md) can restore held notes
automatically when an instrument is replaced or activated. It is optional;
manual Refresh works without installing it. Preset changes inside an unchanged
plug-in may still need a manual refresh.
