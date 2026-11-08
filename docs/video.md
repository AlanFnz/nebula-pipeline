# Working with video

[Documentation](README.md) · [Editing](editing.md) · [Sound](sound.md)

**Import video…** opens a new composition at the footage's aspect ratio and
frame rate. Preparation runs in the background and can be cancelled. The
unsaved composition being left can be saved before switching.

- **Source**, with **Editing: Entire project**, controls the shared In/Out range, uniform scale, X/Y position, rotation and
  Fit / Fill-crop / Original pixel size. Changing the canvas never stretches
  the footage. **Use trimmed duration for timeline** explicitly resizes the
  arrangement; otherwise clip durations continue to determine the total.
- In a video timeline, **+ Add clip…** imports new footage after the active
  clip. Choose **Copy clip** to reuse its effects, automation, framing and
  duration, or **Whole-clip look** to use the current phrase and shared effects
  without local overrides; its duration follows the new footage (up to five minutes).
  New footage uses its full source range at normal speed, with one play.
  Copied framing, cadence and end behavior follow the chosen clip. Canvas,
  FPS and other clips keep their settings. Cancellation adds nothing; Undo
  removes the completed addition in one step. Generated timelines retain
  their existing clip controls in **Arrange clips…**.
- Select a timeline clip and open **Source → Choose video for this clip…**
  to replace only its footage, keeping effects and automation. Alternatively,
  choose **Independent footage · starts at In** to give the same video its own
  trim, framing and cadence. **Use shared footage · continuous** returns the
  clip to the shared source, removing its independent settings; Undo restores
  them. Duplicating an independent clip copies its settings independently;
  local footage starts at In on each clip repeat.
- The clip playback summary shows its length, effective speed and the source
  interval that actually plays, including any hold or loop. **Selected source
  range** shows the available In/Out limits separately: a seven-second clip
  can use only seven seconds of a ten-second range. For repeated clips, the
  summary describes the first play; later shared repeats continue the source clock.
- Shared clips show **Edit shared source** instead of disabled trim/framing
  fields. This switches to Entire project without changing the composition.
  **Make independent for this clip** copies the shared video settings into
  the selected clip so its trim and framing become editable; Undo restores sharing.
- **Playback speed** is available in Source while editing a clip. With
  **Match clip duration to speed** checked, 10 seconds at 1× becomes 5 seconds
  at 2×, including proportional effect and automation timing. Uncheck it to
  change only video speed while retaining the clip duration and effect clocks.
  **Use trimmed duration for this clip** fits the local trim at its current
  speed without changing other clips. Timeline-edge resizing still offers
  **Keep footage speed** and **Stretch footage**.
- **Loop trimmed range** repeats that range. **Hold last frame** freezes its
  last frame. Shared footage time stays continuous across clip boundaries; effects
  can change without restarting the input.
- **Effect cadence** holds shared procedural changes independently of footage playback;
  effects with their own FPS controls retain their independent clocks.
  **Motion cadence** holds the source image at a chosen FPS without changing
  playback speed or duration; **Native FPS** preserves the original behavior.
  **Timeline FPS**, always visible beside Canvas in the workspace header, sets the frame rate of the complete image in both
  preview and export, across every clip. Try 12 or 15 fps for a stepped look;
  it changes sampling rather than slowing the action. Clip durations round
  to the nearest frame. Speed changes are uniform within each clip; speed
  ramps and reverse playback remain future work.
- **Effects** offers applicable image treatments: tape damage, breakup, scan
  drag, drift, ghosts, color separation, interference, exposure flare, jitter,
  bloom, raster/grain/softness, print surface, signal background and low-res
  finish. **Master** adjusts the final brightness, contrast and saturation.
  **Photocopy** and **Subject cutout** add toner printing and local foreground
  extraction. Object generators are not offered for video.
- **Source → Treatment presets** applies looks such as Clean, Worn tape,
  Printed motion, Cold photocopy or the Cyan treatments to the current footage. These replace effects and master settings
  throughout the composition while retaining its source, framing and clips;
  Undo restores the previous treatment. They are separate from generated studies.
- **Before / source** previews the same frame and framing without treatments or
  master grading. Export always includes the enabled treatments.
- **Keep source audio in export** controls footage audio in Source. Uncheck it
  to silence that footage when the output route uses original video audio.
  An attached soundtrack or generated sound has its own output choice; see
  [Sound](sound.md). Footage audio follows each clip's source, trim and speed with preserved pitch;
  muted clips insert silence and Hold pads its end with silence. Footage audio is not played in preview.
  Export is atomic and cannot overwrite the input, including
  a symlink or hard-link alias.
- Save/Open keeps the source file reference and its identity. Missing or changed
  files have a clear relink message. Replace shared footage in Entire project scope,
  or choose a replacement in that clip's Source panel; this retains
  treatments and valid trim settings. The document does not embed the video;
  keep it with the project when moving between machines.

## Duration, speed and FPS

| Intent | Control | Result |
| --- | --- | --- |
| Show more or less source footage at its current speed | Timeline **Resize: Keep footage speed**, then drag the right edge | Clip length changes; effects and automation stretch. Footage stops or loops at Source → Out. |
| Stretch the same source interval over a different duration | Timeline **Resize: Stretch footage**, then drag the right edge | Video, audio, effects and automation retime together. |
| Set a clip's video speed directly | **Source → Playback speed** | With **Match clip duration to speed** checked, the clip and its effects retime; unchecked, the clip length and effect timing stay fixed. |
| Change the whole piece's frame cadence | **Timeline FPS** beside Canvas | Preview and export sample at the new FPS without changing playback speed. |

For example, to extend a seven-second independent clip to ten seconds at
1×, select it, make sure **Source → Out** reaches at least **In + 10 seconds**,
choose **Keep footage speed**, and drag its right edge to ten seconds. If the
source runs out sooner, **When footage ends** determines Hold or Loop; extending
the timeline does not extend the source file. These resize choices apply to the
next edit and do not reset a speed change already made.

## Media, caches and limits

Preview uses lossless, seekable proxies up to 720 pixels under
`~/Library/Caches/Nebula Studio/video-v1/`, with a bounded decoded-frame cache.
Effect changes reuse decoded frames. Proxies are regenerated when needed and
old files are evicted above a 2 GiB disk budget (the newest proxy is retained even
if it alone exceeds that budget). Full-resolution export decodes the original.
Variable-rate footage is sampled onto a deterministic timestamp grid, capped at
120 fps; audio retains real-time duration. Processing and H.264 delivery use the
studio's existing 8-bit RGB/SDR path, not an HDR mastering pipeline.

For several studies or videos in one assembly, use [Montage](native-montage.md).
To treat footage, see [Effects reference](effects-reference.md).
