# Working with video

[Documentation](README.md) · [Editing](editing.md) · [Sound](sound.md)

**Import video** creates a composition using the footage's proportions and FPS.
In **Source**, trim In/Out and adjust framing. Fit, Fill-crop and Original pixel
size preserve proportions. Changing trim does not resize the timeline until you
choose **Use trimmed duration for timeline**.

**+ Add clip…** adds footage after the active clip. **Copy clip** reuses its
local treatment and duration; **Whole-clip look** uses the shared treatment and
the new footage's duration.

Shared footage keeps a continuous source clock across clips. To trim or replace
one clip independently, use **Source → Make independent for this clip** or
**Choose video for this clip…**. Independent footage starts at In on each repeat.
When footage ends, choose Hold last frame or Loop trimmed range.

## Duration, speed and FPS

| Control | Result |
| --- | --- |
| Resize: Keep footage speed | Dragging the edge changes duration and stretches effects, while retaining video speed. |
| Resize: Stretch footage | Retimes footage, retained audio and effects together. |
| Source → Playback speed | Changes speed. Match clip duration to speed also resizes the clip and its effects. |
| Timeline FPS | Changes frame cadence without slowing the action. |

Source Out still limits available footage. Extending a seven-second clip to ten
seconds needs enough source range, or its Hold/Loop behavior takes over.

**Treatment presets** replaces the composition's effects and Master settings,
keeping source, framing and clips. Undo restores the previous treatment.
**Before / source** compares the framed footage without treatments.

## Media, caches and limits

**Keep source audio in export** includes footage audio when the selected output
route uses it. Audio follows trim and speed with pitch preserved; it is not heard
in preview. A soundtrack has its own export choice. See [Sound](sound.md).

Save references the video file. Keep it with the project and relink it if moved.
Preview uses cached proxies; export reads the original and produces 8-bit SDR
H.264. Speed ramps and reverse playback are not supported. Use
[Montage](native-montage.md) to combine footage with independent studies.
