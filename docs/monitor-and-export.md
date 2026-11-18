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

## Monitor controls and status

Below the timeline, timing and playback share a row; preparation and its summary
share the next. They stack in narrow windows. Drag the divider above the timeline
to adjust the monitor's height.

Below the monitor, **Preview resolution** sits with the actual pixel dimensions
and the prepared-frame counter. The counter describes the current playback
scope at that resolution; the strip below the playhead marks which frames are ready.

A spinner indicates an image update or preparation, even while playback is
paused. During export, a stationary pause symbol means preview preparation is
waiting. **Changes pending** means the displayed image has not caught up with
edits. Auto prepare can resume after export; the movie uses the project as it
was when export started. Hover a shortened status to read its full text.

## Prepare frames

Choose a frame count beside **Prepare range**, position the playhead, then prepare.
Near the end, the range starts earlier to keep the requested length. With
**Selected clips**, the count follows the selected clips in playback order.
**Prepare all frames** covers the complete composition. Both use the selected
resolution and temporary lossless storage beyond the memory cache.

**Auto prepare** warms a nearby range within memory limits. With the loop enabled,
subsequent edits refill the remembered range using temporary lossless storage. Preparation does
not start playback. Starting Play without the loop cancels ordinary preparation;
gap filling can continue during playback.

Use **Cancel range** or **Cancel full preview** to stop an explicit request and
keep completed frames. Auto prepare may still warm nearby frames; turn it off
to stop that automatic work. Request the range again to prepare what is missing.

## Loop the longest ready span

Enable **Loop prepared range** and press Play. It repeats the longest continuous
ready span within the playback scope, including frames from earlier requests.
The checkbox does not start or resume preparation elsewhere. Work already in
progress continues; use **Prepare range** or **Prepare all frames** to request more.
It grows as neighboring frames arrive and never crosses a missing or unselected
frame. A longer separate span takes over; equal lengths keep the current loop
stable. With no ready frames, Play waits before starting audio/MIDI, which follows
the original timeline times.

**Prepare range** and **Prepare all frames** choose what to render; they do not
limit the loop to that request. With **Entire timeline** selected, a fully prepared
timeline loops in full even after a smaller request. The range summary separates
the preparation target from the actual loop's times and frame count.

Visual edits, Undo and resolution changes retain the loop choice while affected
frames rebuild. Sound-only edits retain pixels unless audio reactions change the
image. Auto prepare refills the target; with it off, request preparation again.
Seeking outside the loop, changing Playback scope or opening another document
turns the loop off. The loop is not saved and does not change export or clip repeats.

## Fill a gap

Click a dark gap **between two prepared spans** in the strip below the playhead
to prepare its missing frames. Hover highlights the gap and shows its length.
The clicked gap stays highlighted, with its time range, progress and **Cancel**
beside the monitor. The playhead slider, frame count, Playback scope and full
preparation button are disabled until the gap finishes or is cancelled. Playback
can continue. **Cancel** or **Cancel gap** keeps completed frames and also blocks
Auto prepare from restarting the work until a new request or preview edit.
Click the remaining gap to resume. Outer empty regions and unselected clips are
not fillable gaps; use Prepare range there.

**Joined range** names the preparation target. The loop still follows the longest
continuous ready span, so it uses the joined spans only when they are the longest.

Montage's assembly monitor still uses bounded ranges; these controls are available
when editing compositions and Montage blocks.

## Diagnostics

On macOS, logs live in `~/Library/Logs/Nebula Studio/`:

- `studio.log`: console output and errors from the installed app.
- `preview-events.log`: loop changes, requested ranges, preparation batches,
  cancellations and preview invalidation, with times, resolution and ready spans.

The preview log keeps two older files and stays below about 1.5 MB in total.
It records no images, audio or document contents. When reporting a preview bug,
include the time it happened and these logs alongside a screenshot or recording.
If `NEBULA_STATE_DIR` is set, logs go there instead.

## Export details

**Details** beside Export MP4 shows the full document, dimensions, FPS, duration
and audio route. Inside a Montage block, it describes the parent Montage, whose
export uses its soundtrack or silence. Resolve pending sound or timing drafts
before proceeding.

Export MP4 does not save the editable project or capture DAW audio. Monitor mute
and listening level do not change the export. Playback may skip late preview
frames; export renders every frame. H.264 is lossy, so keep the project and media.
