# Editing a piece

[Documentation](README.md) · [First piece](getting-started.md) · [Monitor and export](monitor-and-export.md)

The composer brings together a source, image treatments and a timeline. **Object**
edits generated material; **Source** edits imported footage; **Effects** treats
the image. **Master** adjusts the final brightness, contrast and saturation.
Use [Montage](native-montage.md) when assembling independent studies and footage.

## Scope and inherited settings

**Editing: Entire project** changes shared settings. Clicking a clip selects it
and moves the playhead while retaining that scope. Double-click a clip, or select
it and choose **Editing: Clip**, to edit locally. Clip view separates **Project
effects · inherited** from **Clip effects & overrides**. Explicit local values
take priority over shared ones.

| Label or action | Meaning |
| --- | --- |
| **Animated · Study** | The source recipe changes this value over time. The range is a summary, not an editable constant. |
| **Use fixed value** | Replace that parameter's animation with the proposed value in this scope. Other parameters keep animating. |
| **Following** | The value comes from the parent scope. |
| **↶** | Remove this parameter's local override and follow its parent again. |
| **↶ Follow project** on an effect | Remove local effect settings while retaining its automation. |
| **Restore this effect** | Restore the effect's overrides in the current scope. Unrelated panels keep their settings. |

Numeric displays round for readability while retaining stored precision. Scrolling
moves the panel; it does not turn a focused slider or closed dropdown. Typed values
commit with Enter or focus change; sliders commit on release. Search and group
folding only change the view. Text and Pleated have task-oriented groups described
in [Object inspector](object-inspector.md).

**Object → Position X / Y** moves the generated source and attached treatments in
output-canvas pixels: right/down are positive. Full-canvas noise and tape remain
across the frame. Project position and clip offsets combine; **Reset position**
clears the current scope. Choosing a new source keeps treatments, canvas and
timing. **Source controls…** opens its complete editor; text stays in Text,
Layout and Motion. See [Sources and studies](sources-and-studies.md).

## Clips, duration and repetition

**Arrange clips…** opens the arrangement controls; **Back to editing** restores
your prior inspector view. A clip contains a source phrase, duration and optional
local edits. Phrases repeat to fill their duration; Rhythm controls their internal
changes. The total includes clip repeats and selected-sequence loops.

- Drag a clip body to reorder. Shift-click selects a range; Command-click adds
  individual clips. Dragging one selected clip moves the selection in its order.
  Escape or dropping outside the timeline vertically cancels.
- Drag a clip's right edge to resize. Animation, transitions and timed effects
  stretch proportionally; following clips move to keep a continuous arrangement.
  The edit snaps to output frames and is one undoable action.
- To stretch several clips, select them and drag the right edge of the last
  selected clip. Durations change by the same proportion, rounded to frames;
  unselected clips keep their lengths. With the timeline focused, Command-A
  selects all. A clip is bounded to one frame–300 seconds and the arrangement
  to one hour.
- Video offers **Resize: Keep footage speed** or **Stretch footage**. Both
  stretch effects; only the latter also retimes footage and retained audio.
  Select the mode before resizing. See [video timing](video.md#duration-speed-and-fps).
- The project Duration control extends or trims; it does not proportionally
  stretch animation. Timeline FPS changes sampling cadence, not speed.

Right-click a clip and choose **Loop** to add a repetition. **Repeat count** is
total plays, from 1 to 32; **Remove loop** returns to one. With several clips
selected, loop the sequence in timeline order: 1–2–3 becomes 1–2–3, 1–2–3.
Nonadjacent selections repeat after the last selected member. Pass markers such
as `↻2` identify repeats; clicking one seeks to its occurrence.

Repeats share their original clip's edits and timing. Authored automation
restarts on each repetition; procedural motion and shared video keep continuous
clocks. Independent footage restarts at In. A video's **Loop trimmed range** is a
separate rule for when its source runs out inside a clip.

**Command-D / Duplicate** copies selected clips as one group after the last
selected clip and selects the copies. Copies retain local settings, automation
and individual loops. Fully selected sequence-loop groups get independent copies;
partial selections copy clips without joining the original group. The focused
automation lane instead duplicates its selected gesture into the next free space
in that clip. If it does not fit, lengthen the clip or move a gesture first.

### Shots and detailed sequences

Studies such as **Text / one more try** open in **Shots** view, with thumbnails,
wording and duration. Double-click a card or choose **Edit text** to edit that
clip in Object. **Duration** stretches its optical motion. **Timeline** restores
proportional blocks and automation. A wording change on one shot does not
replace other shots that happen to contain the same words.

**Open detailed copy…** opens generated events and full parameters in an
independent window. Editing the copy leaves the composition intact. **Use this
sequence in composer** brings it back as a single phrase. The detailed editor
does not have the composer's Undo/Redo history; keep separate saved versions.

## Effects and animation

The Effects overview shows treatments in the selected scope with **On**,
**Intermittent** and **Bypassed** badges. Sources have their own group. Open an
effect for its controls; **Back to effects** returns to the overview.

**Add effect…** opens a searchable library of compatible treatments and presets.
In Entire project it is labelled **Add project effect…**. Browsing does not edit
the piece. Wait for a successful still preview, compare **Before / Preview**, then
choose **Apply effect**. **Play preview** prepares an audition at the selected monitor resolution, including Full canvas,
with up to 12 sampled frames per second. Its length is bounded by the frame
cache. It does not change Timeline FPS or monitor preferences. Cancel/Escape leaves the project unchanged. Applied effects
also offer **Preview preset…** and **Replace with preset**; a bypassed effect stays
bypassed until resumed.

**How this look is built** opens each contribution's controls and can **Compare
without this effect** without adding an undo entry. Explanations distinguish an
effect being off, zero strength and missing source dependencies. Brightness advice
is guidance, not a measurement of every intermediate image.

**Intensity** blends the treatment's contribution: 0% removes it and 100% keeps
its full configured result. It does not rewrite Mix, Strength or other controls.
Sources use their own controls. Intensity follows scope, can be animated in
percentage points, and stays available during search. Some compound treatments
and intermediate Low-res finish intensities require an extra render.

**Bypass / Resume** retains settings and activation timing. **Remove** clears the
effect and its automation. Removing it in Entire project also clears clip
overrides; removing it locally leaves other clips alone. Undo restores it.
**Activation & preset** selects Follow study, On throughout scope or Off
throughout scope. Bypass takes priority over activation and automation.

### Processing order and instances

In Entire project, drag an image effect's six-dot handle to change the processing
order. Effects run top to bottom. The handle also offers **Move earlier / Move
later**, or Option-Up/Down when focused. Escape cancels; Undo restores the order.
**Study order** returns to the embedded recipe's processing while retaining edits.
Order is shared across clips; clip view follows it.

Color field, Granular halo, Subject cutout and Low-res finish have fixed source
or output roles and explain them in tooltips. Broadcast's explicit early polarity
stays before image treatments; its screen/static pass follows the list. Ghosts'
companion form stays with the source while its image trails follow the list.
Transitions and Master retain their final roles. Custom orders require 0.33.0+.

**Tape damage → Add instance**, or **Add another instance** in the browser,
creates another neutral independent pass. Each has parameters, intensity,
bypass and automation. New passes run in creation order after established
image effects until reordered. Tape supports up to 64 slots; other families
currently have one instance each.

For a clean temporary pull, use **Clean pull / animate**, then animate Horizontal
pull. **Pull edges → Keep canvas filled** holds frame edges and stretches the
interior; **Allow blanking** keeps the older displacement behavior. This setting
only controls Horizontal pull.

### Timed gestures

Choose **Animate…** beside a supported parameter. Set target clip, Start, Rise,
Hold, Recover, signed Change amount, Easing and Enabled, then **Apply**. The shown
parameter remains its base. Automation adds a temporary change and returns to
the moving recipe. Cancel leaves the project unchanged.

**Automations…** lists gestures for editing, disabling or removal. Their lane
appears below the clips: double-click to edit, drag to move, or right-click for
actions. Repeated occurrences share one authored gesture. Clip resizing scales
timing in either video resize mode. Overlapping enabled gestures on the same
target are rejected; disabled gestures keep their values.

Bypass and preset replacement preserve gestures; Remove effect clears them.
Restoring a parameter changes its base only. Not every numeric control is an
automation target: look for Animate beside that control. Seeds, source changes,
discrete choices, timing clocks and Master are excluded. The original
[target list](timed-effect-automation-delivery.md#shipped-targets) is a historical
baseline; later treatments add targets through their metadata.

For recorded project-wide gestures, see [Visual performance](visual-performance.md).
For soundtrack-driven continuous responses, see [Sound](sound.md#import-a-soundtrack-and-make-visuals-react).

## Variations and comparison

**Creative** in Tape damage, Frame jitter, Ghosts and Particles adjusts their
existing animation. Most controls use 100% as neutral; Ghosts copy adjustment
uses zero. Each control explains its affected values and bounds. Pattern cadence,
movement speed and Timeline FPS are separate. Local neutral values can cancel
an inherited creative adjustment. **↶ / Restore creative controls** follows the
parent while retaining explicit fixed values.

**Creative → Vary this effect…** auditions Subtle, Moderate or Strong changes
in these four pilots. Choose what may vary; timing starts unchecked. Each Try
starts from the captured base. **Keep variation** makes one undoable edit;
Discard leaves the piece unchanged. Keep or discard before saving/exporting.
The wider **New variation** command honors **Keep** locks on macros and retains
fixed effect parameters.

**Snapshots…** beside View zoom stores complete named compositions in the current
document. **Compare with B** compares snapshot A with working B at the same time
and quality; **Restore as working B** restores its source, canvas, effects and
timing. Incompatible canvas/FPS/time maps prevent direct comparison but still
allow restoration. Export B MP4 exports the working composition even while
viewing A. A real edit returns to B. Snapshots support removal, Undo and Save.

## Master, canvas and monitoring

**Master** always affects the whole composition: Brightness starts at 0%,
Contrast and Saturation at 100%. Saturation 0% makes black and white. **Enable
master** bypasses without losing values; **↶ / Reset master** restores neutral.
Master processes the finished image, including backgrounds and transitions,
before Low-res finish enlargement. Relative **Finishing** controls instead modify
the recipe; 1× retains each clip's authored values.

**Output canvas** changes the authored frame. Formats include 720×576, 1080×1920,
1080×1350, 1080×1080, 1080×1440, 1080×566 and 1920×1080. Loaded custom sizes are
retained. By default resizing preserves artwork dimensions and proportions,
revealing or cropping space around it. **Fit content** uniformly fits the artwork's
reference canvas inside the output. Neither stretches one axis independently.

**View zoom / Fit view** only magnifies the monitor. Scroll over the image to
zoom around the pointer; drag or Shift-scroll to pan and double-click to fit.
**Preview resolution** controls monitor sampling; export uses full output size.
Choose **Entire timeline** or **Selected clips** for playback. Selected clips
play all their occurrences at their original absolute times, skipping other
clips; export still includes the whole document.

**Prepare range** fills a bounded preview window. **Prepare all frames** prepares
the complete composition using temporary lossless disk storage beyond its RAM
budget. Cancel retains completed frames for resume. Preparing does not start
playback or change export. **Auto prepare** warms nearby frames after edits or
scrubbing. Global visual changes invalidate relevant prepared frames; sound-only
edits retain them. See [Monitor and export](monitor-and-export.md).

Drag the dividers to resize the monitor and inspector. Workspace size, splits,
zoom and full-screen state are preferences separate from project output.

## Save and manage studies

The document name and an asterisk identify unsaved changes. **Save** writes the
associated file, asking for a path on first use. **Save As…** asks for a new path.
Loading a study/importing footage starts a document without binding Save to the
original asset. Save validates and applies pending text drafts. Sound has its own
[apply/save decision](sound.md#listen-apply-save-and-export). MP4 export does not
save the editable project.

**Save ▾ → Save as study…** creates an independent library snapshot of the
composition, including source recipe, clips, effects, canvas, timing and master.
Personal studies live under `~/Library/Application Support/Nebula Studio/Studies/`.
Video and soundtrack assets used by the piece and its snapshots are copied once
and referenced relatively. Copy the whole study folder when moving it. Fonts
from the system remain external dependencies. Saving publishes the study folder
only after its contents are complete; failure/cancellation leaves the library
intact. Edits made while an asynchronous save runs remain unsaved.

**Browse…** opens the visual study library with search, categories, dates and
favorites. Still previews render for selected/visible entries; failed thumbnails
do not prevent loading. **Remove selected** hides entries without deleting their
media; **Removed studies → Restore selected** brings them back. Removal does not
reclaim disk space. Built-in recipes and personal media are separate from library
visibility preferences. Personal dates record the original save; older entries
may use file creation/modification dates, identified in the date tooltip.

## Keyboard reference

These shortcuts apply when the viewer or timeline has focus; text/numeric fields
retain their editing keys. The menus show platform-specific equivalents.

| macOS shortcut | Action |
| --- | --- |
| Command-N / Command-O | New piece / Open |
| Command-S / Command-Shift-S | Save / Save As |
| Command-Z / Command-Shift-Z | Undo / Redo |
| Space | Play / Pause |
| Left / Right | Step one output frame |
| Shift-Left / Shift-Right | Step ten output frames |
| Command-A in timeline | Select all clips |
| Command-D in timeline/automation lane | Duplicate selection |
| Escape during a drag | Cancel the drag |

Montage and the sound step grid have their own navigation shortcuts. Read their
respective guides before treating a timeline key as a global command.
