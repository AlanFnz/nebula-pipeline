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

If playback skips, lower Preview resolution and prepare frames. **Prepare range**
caches a bounded region; **Prepare all frames** prepares the complete composition
using temporary storage. Preparing does not start playback. The counter names
the scope and reports partial or complete coverage. Montage uses bounded ranges.
Visual edits can invalidate prepared frames; sound-only changes keep them.

## Export details

**Details** beside Export MP4 shows the full document, dimensions, FPS, duration
and audio route. Inside a Montage block, it describes the parent Montage, whose
export uses its soundtrack or silence. Resolve pending sound or timing drafts
before proceeding.

Export MP4 does not save the editable project or capture DAW audio. Monitor mute
and listening level do not change the export. Playback may skip late preview
frames; export renders every frame. H.264 is lossy, so keep the project and media.
