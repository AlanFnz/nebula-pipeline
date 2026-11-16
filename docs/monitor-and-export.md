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
Enable **Loop prepared range** at any time and press Play. It repeats the longest
continuous prepared span within the playback scope, including frames from earlier
requests. It grows as neighboring frames arrive and never jumps across a gap.
If another separate span becomes longer, the loop switches to it; equal lengths
keep the current loop stable.
If none are ready yet, playback waits for the first one. Audio/MIDI follows the
displayed timeline times. The counter shows preparation progress; the loop does
not change export or clip repeats. Seeking outside the current loop exits it.

**Auto prepare** warms a nearby range within memory limits; with the loop enabled,
it finishes that fixed range using temporary lossless storage. **Prepare all frames**
prepares the complete composition. Preparing does not start playback. Visual edits
or resolution changes rebuild affected frames while keeping the loop enabled;
sound-only changes keep prepared pixels. With Auto prepare enabled, the loop fills
again automatically. Otherwise, click Prepare range or Prepare all frames to rebuild.

**Prepare range** and **Prepare all frames** choose what to render; they do not
limit the loop to that request. A fully prepared timeline loops in full, even
after a smaller preparation request. Cancelling keeps completed frames available.
The summary shows the preparation target and the actual loop's times and frame
count separately. Opening another document resets the preview loop.

Click a dark gap **between two prepared spans** in the strip below the playhead
to prepare only the missing frames at the selected resolution. Hover highlights
the gap and shows its length. With **Loop prepared range** enabled, the current
loop grows through contiguous new frames, then covers both spans when they join.
The clicked gap stays highlighted, with its time range, progress and **Cancel**
beside the monitor. Choosing another range is disabled while it prepares;
playback can continue. Cancel keeps completed frames and stops preparation,
including Auto prepare, until you request another range or edit the preview.
Click the remaining gap to resume.

The summary calls the result a **Joined range**. Once preparation finishes or
is cancelled, you can fill another gap. This changes only preview playback,
not the project or export.

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
