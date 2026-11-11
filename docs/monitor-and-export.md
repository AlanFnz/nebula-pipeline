# Monitor and export

[Documentation](README.md) · [Sound routes](sound.md)

## View, preview and output

| Control | What changes |
| --- | --- |
| Output canvas / Fit content | Finished frame and artwork framing. |
| View zoom / Fit view | Display magnification only. |
| Preview resolution | Monitor detail: 360 px, 720 px or Full canvas. |
| Timeline FPS | Frame cadence in preview and export. |

Export uses the whole document at its output canvas and FPS, regardless of
preview quality, zoom or selected playback clips. **Low-res finish** is an
authored effect, so it does affect export.

## Preparation

Choose a frame count beside **Prepare range**, position the playhead, then prepare.
The range uses the selected resolution and temporary lossless storage, even when
it exceeds memory. Near the end it starts earlier to keep the requested length.
When ready, enable **Loop prepared range** and press Play. The displayed range
repeats with audio/MIDI following its timeline times; this does not change export
or clip repeats. Seeking outside the range exits its loop.

**Auto prepare** warms a nearby range within memory limits. **Prepare all frames**
prepares the complete composition. Preparing does not start playback. Visual edits
or resolution changes can invalidate the range; sound-only changes keep it.
Montage's assembly monitor still uses bounded ranges; these controls are available
when editing compositions and Montage blocks.

## Export details

**Details** beside Export MP4 shows the full document, dimensions, FPS, duration
and audio route. Inside a Montage block, it describes the parent Montage, whose
export uses its soundtrack or silence. Resolve pending sound or timing drafts
before proceeding.

Export MP4 does not save the editable project or capture DAW audio. Monitor mute
and listening level do not change the export. Playback may skip late preview
frames; export renders every frame. H.264 is lossy, so keep the project and media.
