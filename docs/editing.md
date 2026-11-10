# Editing a piece

[Documentation](README.md) · [First piece](getting-started.md)

Object edits generated material, Source edits footage, Effects treats the image,
and Master adjusts the finished image. Use [Montage](native-montage.md) to assemble
independent studies and footage.

## Scope and inherited settings

The inspector header names the composition or Montage block and its file status.
The line above the timeline separates **Selected**, **Editing** and **Playback**:
selection chooses arrangement actions; the inspector scope chooses what edits
affect; Playback chooses the range to play. Long document names are available on
hover or keyboard focus.

**Editing: Composition** changes shared settings. Double-click a clip to edit
it locally; an ordinary click selects it and seeks. Clip overrides take priority.
Master, Perform and shared Ink timing affect all clips. Their header states that
scope and disables the remembered **Return scope** until you leave that panel.
Inside Montage, “all internal clips” refers only to the block being edited.

**Base · Study animation** and **Study range** describe the recipe, before clip
automation and Perform. **Monitor** shows a read-only value at the displayed
time, its clip and any additional modifiers. It never replaces the editor's base.
If you are editing another clip, the monitor annotation says so.

**Use fixed value** sets the proposed **Fixed base** in this scope; it does not
sample the playhead or remove clip automation or Perform. **↶** removes only the
local base override and follows its parent again. **Value sources** beside the
scope selector explains the order. Search and group folding only change the view.

Active or bypassed Perform adjustments appear above the inspector tabs, with
**Open Perform** to reach them. Recorded knobs are labeled **Recorded movement**;
editing one with Record off replaces that knob's recording. Undo restores it.
Audio-responsive parameters show their monitor value **before audio response**.

Changing the generated source keeps treatments, canvas and timing. For source
controls, see [Sources and studies](sources-and-studies.md) and
[Object inspector](object-inspector.md).

## Clips, duration and repetition

Select a clip in **Timeline** or **Shots**. Directly below it, **Duration** changes
the length of one play and **Repeat** sets how many times it plays: 1× = once,
2× = twice. The calculation shows the resulting clip duration; for example,
**6 s × 2 = 12 s**. Repeat keeps the timing of each play. Command-Z undoes either edit.

Drag a clip to reorder it or its right edge to resize it. Resizing stretches
animation and timed effects. Shift-click selects a range; Command-click adds
individual clips. To stretch a selection, drag the last selected clip's right edge.
Command-D duplicates the selection; Escape cancels a drag.

Right-click **Loop** repeats a clip or selected sequence. Repeats share edits;
duplicates can be edited independently. **Duration & loops** opens the inspector's
timing and arrangement panel; its name stays the same while open. **Done** returns
to the object/effects inspector. **Retime total duration** stretches the whole
arrangement, while Timeline FPS changes frame cadence without changing speed.
[Video](video.md#duration-speed-and-fps) has separate speed and resize choices.

### Shots and detailed sequences

In Shots view, double-click a card to edit its wording. **Timeline** returns to
proportional blocks. **Open detailed copy…** opens an independent event editor;
it has no composer Undo/Redo history, so keep separate saved versions.

## Effects and animation

Use **Add shared effect…** or **Add clip effect…**, preview a preset, then choose
**Apply effect**. Browsing does not edit the piece. **Intensity** blends the
contribution; **Bypass / Resume** keeps settings. **Remove** clears the effect
and its automation in the selected scope. Removing a project effect also clears
its clip overrides. Undo restores it.

**How this look is built** opens the controls behind the current treatment.
See the [effects reference](effects-reference.md) for choosing one.

### Processing order and instances

In Composition, drag an effect's six-dot handle to change order. Image effects
run top to bottom; source/output stages keep their fixed roles. **Study order**
restores the recipe's order. **Tape damage → Add instance** adds an independent
pass; other effect families currently have one instance each.

### Timed gestures

Choose **Animate…** beside a supported control. Set the target clip, Start, Rise,
Hold, Recover and Change amount, then Apply. The gesture adds to the base value
and returns to it. Use **Automations** or the timeline lane to edit it.
Overlapping enabled gestures on the same target are rejected.

For recorded gestures, see [Visual performance](visual-performance.md). For
soundtrack-driven changes, see [Sound](sound.md#import-a-soundtrack-and-make-visuals-react).

## Variations and comparison

Tape damage, Frame jitter, Ghosts and Particles have **Creative** controls and
**Vary this effect…**. Try a variation, then Keep or Discard before saving/exporting.

**Snapshots** stores named compositions inside the document. **Compare with B**
compares a snapshot with the working piece at the same time and quality when
their canvas and timing are compatible. **Restore as working B** restores one.
Export B MP4 always exports the working piece.

## Master, canvas and monitoring

Master affects the whole image. **Output canvas** sets the finished frame;
**Fit content** fits the artwork proportionally. View zoom only magnifies the
monitor. Preview resolution affects on-screen detail, while export uses the full
canvas. See [Monitor and export](monitor-and-export.md).

## Save and manage studies

**Save** writes the editable document; **Save As…** keeps another version.
**Save ▾ → Save as study…** makes a library snapshot and copies referenced video
and soundtrack media. System fonts remain external. Sound drafts have a separate
[apply/save decision](sound.md#listen-apply-save-and-export).

**Browse** opens study previews and search. **Remove selected** hides a library
entry without deleting its media; **Removed studies → Restore selected** brings
it back. Copy the entire personal-study folder when moving it.

## Keyboard reference

With the viewer/timeline focused: Space plays/pauses, Left/Right steps frames,
Command-A selects all clips, Command-D duplicates, and Command-Z undoes.
Command-S saves. Text fields retain their own editing keys; menus show the
platform's shortcuts.
