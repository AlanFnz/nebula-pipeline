# Native montage

Open **Montage…** in the header (or File → Open in Montage) to arrange the
current study alongside footage. The study becomes an embedded, editable copy.
Montage replaces the workspace in the same Nebula window.
Existing composition files still use their original renderer. Montage documents
use `format: nebula-montage`, version 1; Open recognizes both formats.

Import videos or composition JSON files into Material. Material source and Target
block are separate selections, named beside their controls. Choosing material or
moving the playhead does not change the target. Multi-selection keeps bulk actions
available; single-block timing, editing and replacement require exactly one target.

Use **Insert range…** (or double-click Material) to preview and set In/Out with
the buttons or I/O. Out is exclusive. The dialog names its insertion boundary:
after the selected block(s), or at the end when there is no selection. Dropping
Material on the timeline uses that drop boundary. It does not split at the playhead.
Range frames use the montage FPS, even when the source FPS differs; both rates
and the resulting duration are shown. The source stays intact. The library
displays usage counts. Undo/Redo restores the selection with the document edit.

Use the **Block list** tab beside Material to find short shots by name, number or
source material. Each row wraps the full name and shows its kind, timeline start,
duration in frames/seconds, and material. Selecting a row selects and reveals that
timeline block without moving the playhead or starting playback; Enter or a double
click opens its existing editor. Multiple selection and pending timing drafts use
the same rules as the timeline. Search only filters the list and does not change
the selection or document.

Timeline blocks retain their proportional widths. Labels show the block number
and as much of its name as fits; the selected-block strip and hover details show
the full information, including for cuts too narrow to carry a number. Numbers
follow timeline order after reorder and Undo/Redo; operations still use block IDs.
**Show selected block** adjusts zoom and scroll explicitly; **Previous view**
returns to the prior zoom and scroll. Neither operation changes playback, source
ranges or document history. Marker selection reveals its full name beneath the
marker list without seeking; double-click retains the existing seek action.

Drag timeline clips to reorder; Shift-click selects several. Drag a right edge
to change duration. With snapping enabled it attaches to nearby music markers.
Split uses the playhead. Duplicate preserves the selected sequence's order.
With the timeline focused, arrows select adjacent clips, Home/End select the
first/last clip, and Return opens its editor.
Source In slips the range without moving the cut; timing changes are checked
against source bounds. Every document edit can be undone/redone.
With no single target, the inspector shows an empty timing state instead of the
previous block's numbers. Typing In, Duration or Speed creates a named timing
draft. **Apply timing** updates that block; **Revert timing draft** restores its
applied values. Before changing target, editing a block, saving, exporting or
leaving, resolve a pending draft with Apply / Discard / Stay. Applying is distinct
from saving the file. Preview continues to use the applied timing until Apply.

To replace a shot, select one timeline block and a library item, then **Replace
target block…**. The dialog names source and target. Pick a new In point; the
existing duration/speed and treatment are kept, and Out is calculated. The last
sample must fit inside the source, matching the renderer's existing boundary
rule; an insufficient range disables replacement and explains why. Cancel leaves
the document intact and Undo restores the prior source. Copy treatment / Apply treatment to selection transfers the current look
without copying wording or source objects. A copied animated recipe is sampled
at the chosen clip's starting frame; explicit overrides remain overrides.

Double-click a timeline block or use Edit study / effects to enter that block in
the same window. The breadcrumb identifies the project and block. **Back to
montage** (Cmd+[ on macOS) validates and keeps the edits, returning to the same
selection, playhead and timeline zoom. Montage Undo reverses the block edit.
An unedited visit leaves the document unchanged. A study's own duration must
still cover its selected montage range; invalid changes stay open for correction.
Library snapshots and other clips are not changed by editing one block.

**Save** and **Export montage** in the block editor include the complete project,
including pending text edits. Closing the window or opening another document
offers Save / Discard / Cancel for the complete montage. Export returns to the
montage so its progress and Cancel button remain visible.

Soundtrack is a single absolute project track. Add named markers at the playhead
to identify musical cuts. Markers stay on the music when clips move. Double-click
a marker to seek. Waveform and clips share the same zoom and scroll position.
Export supports soundtrack or silence; nested source audio is
not mixed. Audio reactivity can still be authored inside an individual study.

The monitor has explicit 360 px / 720 px / Full canvas detail. Prepare caches a
bounded region at that selected detail. Playback drops late video frames rather
than slowing the soundtrack. Export always uses the full montage canvas, with
each study fitted proportionally. Choose a portrait study/canvas before opening
Montage to start a portrait assembly.
The selected monitor detail follows navigation into and out of block editing;
hidden contexts pause playback and background preview preparation.

## Reproducibility

Clips store a source In frame, duration frames, speed and an asset snapshot or
local edited copy. `MontageRenderer` compiles each distinct snapshot once and
renders at its source-local time. Parent placement never changes that clock.
The monitor and exporter use this same renderer. Source media paths remain
external and are resolved relative to the document on load; keep the media with
the project. Save and export refuse to replace source media. Export is atomic
and cancellation preserves an existing destination.

The Guerrilla Radio acceptance project embeds the editable v08 introduction and
30 native shot recipes with their original optical clock offsets. It retains
the approved portrait excerpts, with the full originals separately available in
Material for new selections. No rendered introduction or final montage is used
as the source. The earlier approved MP4 remains the comparison reference.

Compression can produce different H.264 bytes from the earlier chunked export;
the frame content, timing, cuts and audio are compared separately. This release
does not claim bit-identical compressed files or automatic shot selection.
