# Monitor and export

[Documentation](README.md) · [Editing](editing.md) · [Sound routes](sound.md)

Use Output canvas for the finished frame, Preview resolution for the image
Nebula prepares on screen, and View zoom for its displayed size.

## View, preview and output

- Output canvas and Fit content control the authored frame and content framing.
- View zoom and Fit view only change display magnification. Numeric zoom remains
  persistent; opening a document does not force Fit view or alter its framing.
- Preview resolution limits the longest edge to 360 or 720 pixels without
  enlarging small canvases. Full canvas uses the authored dimensions. The monitor
  shows the resulting pixel dimensions beside this selector.
- Export renders the complete document at the output canvas and FPS regardless
  of preview resolution, preparation, zoom or selected playback clips. Authored
  Low-res finish and other treatments retain their existing behavior.

## Preparation

Prepared-frame counters name their scope: Timeline, Selected clips, Block
composition or Montage. Counts use only valid cached frames at the current
resolution/revision. A ready bounded range does not claim that the entire scope
is prepared, even when the scheduler could fit more frames in memory. A zero-frame
range caused by the memory budget is explicitly unprepared, with guidance in its
help. Preparation and Play remain separate actions.

Prepare range retains the existing bounded preparation. Prepare all frames in
composition and sound editors still uses temporary lossless disk storage for the
whole composition, independently of selected playback clips. Montage retains its
bounded preparation and reports the prepared time range and montage-wide count.
Changing Montage preview resolution cancels preparation for the old resolution;
late callbacks cannot announce readiness for the new one. Cached pixels remain
partitioned by resolution and revision.

## Export details

Details beside Export MP4 opens an optional, read-only summary. Direct Export MP4
and existing shortcuts still work without visiting it. The summary names the
complete document, canvas, FPS, duration derived from encoded frames, frame count,
MP4/H.264 format and applied audio route. Odd canvas dimensions disclose the
encoder's existing even-pixel padding.

Inside a Montage block, the summary describes the parent montage, as Export does.
It explicitly names the montage soundtrack route; generated/block source audio
is not mixed by the current montage exporter. Unapplied timing or sound drafts
are identified without changing them. Export retains its existing apply/revert
or applied-sound choice. Monitor mute and audition level do not change this route.


Export does not save the editable project. Save first if you want to retain the
current composition as a file. H.264 is lossy; a finished MP4 is not a replacement
for project JSON and its source media. Playback can drop preview frames under
load while export renders every frame. Imported soundtrack and generated-sound
monitoring are audible; a video's original audio is currently export-only.
