# Nebula Studio

A native Python + PySide6 desktop app for experimenting with the existing digital print, scan, motion and grading effects. Open a clip, adjust its treatment, scrub, compare versions, and play a short loop inside the app.

The project version comes from [`_version.py`](_version.py); run `python studio.py --version` to display it. See [versioning](VERSIONING.md) and the [changelog](CHANGELOG.md) for milestone history and compatibility notes.

The [reusable effects plan](docs/reusable-effects-plan.md) tracks the incremental
separation of objects, regions and treatments. The first milestone adds reusable
directional regions and versioned compatibility, with all nine original study
results protected by raw-pixel regression tests.

## Launch on this Mac

The installed **Nebula Studio.app** lives in `~/Applications`. Open it in Finder
or click its Dock icon; it opens the visual synthesizer directly. Python, Qt,
the renderer, presets and icons are inside the app, so it does not need to read
the development environment under Documents. FFmpeg remains a local dependency
installed through Homebrew. Startup errors are recorded in
`~/Library/Logs/Nebula Studio/studio.log`.

To build or update the app from a checkout on this Mac:

```sh
cd nebula-pipeline
.venv/bin/python -m pip install -r requirements-build.txt
.venv/bin/python scripts/build_macos.py --install
```

Quit the installed app before updating it. The installer stages and verifies a
complete bundle, preserves any previous installation as a dated backup, then
replaces the app. Builds are snapshots: rebuild after source changes. Without
`--install`, the result stays in `dist/Nebula Studio.app`. Generated bundles and
build intermediates are ignored by Git. The bundle is signed ad hoc for local
use on the build Mac; it is not a notarized distribution for other computers.
The build uses [PyInstaller's macOS bundle support](https://pyinstaller.org/en/stable/spec-files.html).

For a fresh checkout, install Python 3.11+ and FFmpeg, then create the isolated environment once:

```sh
brew install python ffmpeg
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-desktop.txt
.venv/bin/python studio.py
```

The development entry point remains available without building an app:
`studio.py --synth` opens the synthesizer; `studio.py` opens the input-clip editor.
The installed app also accepts `--clip-studio` to open that editor. The Python
entry point works on other platforms with PySide6 and FFmpeg on PATH; this
milestone was validated on macOS with Python 3.14 and PySide6 6.11.2. Optional startup arguments:

```sh
.venv/bin/python studio.py /path/to/clip.mp4 --preset /path/to/settings.json
```

## Source-free visual synthesis

The desktop studio also includes a native generator for the luminous slabs and
irregular Venetian-blind rays in the reference study. Launch it with:

```sh
.venv/bin/python studio.py --synth
```

The Synth window supports deterministic continuous animation, treatment FPS
holds, separate export FPS, module enable/order controls, typed parameter
editors, per-parameter variation locks, curated presets, JSON round trips and
atomic MP4 loop export. The schema and renderer live in [`synth.py`](synth.py);
new effects register one module specification and one renderer callback in
`RENDERERS`. Unknown modules survive save/reload for forward compatibility.

The composer also accepts normal video as an image source through **Import
video…**, alongside the generated studies. The earlier Print → Scan clip editor
remains available from the same `studio.py` entry point.

### Video sources in the composer

**Import video…** opens a new composition at the footage's aspect ratio and
frame rate. Preparation runs in the background and can be cancelled. The
composition being left is backed up in
`~/Library/Application Support/Nebula Studio/Backups/` before switching.

- **Source** controls the global In/Out range, uniform scale, X/Y position and
  Fit / Fill-crop / Original pixel size. Changing the canvas never stretches
  the footage. **Use trimmed duration for timeline** explicitly resizes the
  arrangement; otherwise section durations continue to determine the total.
- **Loop trimmed range** repeats that range. **Hold last frame** freezes its
  last frame. Footage time stays continuous across section boundaries; effects
  can change without restarting the input.
- **Effect cadence** holds procedural changes independently of footage playback.
  **Motion cadence** holds the source image at a chosen FPS without changing
  playback speed or duration; **Native FPS** preserves the original behavior.
  **Arrange → Export frame rate** controls delivered frames. Source playback is
  real time; this milestone does not add speed ramps or reverse playback.
- **Effects** offers applicable image treatments: tape damage, breakup, scan
  drag, drift, ghosts, color separation, interference, exposure flare, jitter,
  bloom, raster/grain/softness, print surface, signal background and low-res
  finish. **Master** adjusts the final brightness, contrast and saturation.
  **Photocopy** and **Subject cutout** add toner printing and local foreground
  extraction. Object generators are not offered for video.
- **Source → Treatment presets** applies Clean, Worn tape, Printed motion or
  Soft signal or Cold photocopy to the current footage. These replace effects and master settings
  throughout the composition while retaining its source, framing and sections;
  Undo restores the previous treatment. They are separate from generated studies.
- **Before / source** previews the same frame and framing without treatments or
  master grading. Export always includes the enabled treatments.
- **Keep source audio in export** is explicit in Source. Uncheck it for a silent
  MP4. Audio follows the trimmed loop; Hold pads its end with silence. The preview
  is currently silent. Export is atomic and cannot overwrite the input, including
  a symlink or hard-link alias.
- Save/Open keeps the source file reference and its identity. Missing or changed
  files have a clear relink message: **Source → Relink / replace video…** retains
  treatments and valid trim settings. The document does not embed the video;
  keep it with the project when moving between machines.

Preview uses lossless, seekable proxies up to 720 pixels under
`~/Library/Caches/Nebula Studio/video-v1/`, with a bounded decoded-frame cache.
Effect changes reuse decoded frames. Proxies are regenerated when needed and
old files are evicted above a 2 GiB disk budget (the newest proxy is retained even
if it alone exceeds that budget). Full-resolution export decodes the original.
Variable-rate footage is sampled onto a deterministic timestamp grid, capped at
120 fps; audio retains real-time duration. Processing and H.264 delivery use the
studio's existing 8-bit RGB/SDR path, not an HDR mastering pipeline.

Video compositions and compiled sequences use storage schema 2 so older builds
reject them explicitly; generated documents retain schema 1 and their render
versions, defaults and seeds. Pixel contracts cover all eleven studies,
including both newer profile models. `synth_video.py` owns source identity,
framing, clocks and decoding; `synth_video_audio.py` handles audio assembly.
The existing renderer accepts an optional source image before the same image
treatments. Tracked object identities, input-driven particles and
multiple footage layers remain future work.

### Editable text studies

Four six-second Studies use the editable phrase **REVOLUTION IS NOW**:
**Text / phosphor drift**, **Text / pressure**, **Text / lost transmission**,
and **Text / night monitor**. They combine the same Bloom, Raster/grain,
Tape damage, Frame jitter, Color separation, Signal drift and Low-res finish
operations used elsewhere in the Studio. Original recipes remain frozen in
`presets/text-studies-v1.json`; all eleven earlier studies stay unchanged.
The refined **Pressure** uses single-word, tall poster lettering, a half-second
perspective pullback, overlapping positive/negative exposures and composite
color fringes. It is frozen separately in `presets/text-pressure-v2.json`.
The other three refined recipes are frozen in `presets/text-studies-v2.json`:
Phosphor drift uses green-white lettering, changing teal/blue exposure washes
and broken-sync interruptions; Lost transmission uses repeated word groups,
red introductions, chromatic ghosts and cream/magenta inversions; Night monitor
uses smaller white type, blue halation and a worn CRT aperture. Their canvas
proportions and held frame rates follow the individual references.
All four **(first version)** entries remain in Studies, including the original
stacked-title Pressure. Saved documents keep their original rendering.

Choose **Object → Text** to replace a generated source and retain its image
treatments, or load a text Study. Edit **Wording**, then **Apply text**. Text
supports eight lines and 512 characters. Typeface, size, line/letter spacing,
alignment, color, opacity, intentional width/height stretch and rotation remain
editable. Object X/Y moves the lettering and its source-bound effects. Canvas
resizing uses the existing preserve/fit rules and never stretches the type.
**Text fitting → Fill block** deliberately fits lettering into an authored
rectangle: **Block width** and **Text size** set its proportions. This is separate
from canvas resizing and is useful for very tall, compressed poster type.
**Text copies** and **Copy spacing** repeat the lettering as one movable group.
**Line width limit** uniformly shrinks long groups in Fit long lines mode,
keeping repeated words readable within their intended part of the canvas.
**Wrap after characters** inserts configurable line breaks, preferring spaces
and splitting long words; zero preserves manual breaks. Word reveals still
advance through the original words, and type-on retains the original character
clock and stable layout. **Repeat size floor** reduces duplicate copies before
fitting would shrink the type below the chosen fraction of Text size; zero
keeps all copies. A single copy can still shrink to honor Line width limit.
Lost transmission keeps each word on one centered line, using Text size, Width
stretch and Line width limit to give long words nearly the full canvas width.
Repeat size floor reduces copies when needed, keeping shorter words large too.
Automatic wrapping is off in this study. Its updated layout is frozen in
`presets/text-transmission-v4.json`; earlier snapshots and saved documents
retain their existing layouts.
Four bundled fonts (Archivo Black, Anton, Space Mono Bold and Bodoni Moda) render identically
without depending on installed system fonts; their licenses and pinned source
hashes are in [`assets/fonts`](assets/fonts/README.md).

**Text / opium · 4.5s** adds a monochrome study with three exposure pulses.
Change **Object → Wording → Apply text** to replace OPIUM; the bold center and
stretched serif copy share that wording. Its recipe is frozen independently in
`presets/text-opium-v1.json`.

- **Stretch echo** controls the vertical/horizontal stretch, contour or solid
  fill, copies, brightness and color. Its animation can open/reset, breathe or
  hold still. Cycle seconds, starting stretch, easing and Motion FPS control
  the movement. For text, Echo typeface can use an alternate bundled font.
- **Signal etch** controls horizontal grain, edge displacement, erosion and
  scattered light. Solid ink retention protects thick strokes. Exposure pulse,
  Pulse cycle seconds, duration, vertical stretch and spread shape each flash;
  Texture FPS holds only the noise. Set exposure pulse to zero to stop flashes.

Both treatments work on objects and footage as well as text, after the source
generators and before finishing effects. Object position and canvas reframing
keep the echo attached. When combined, the exposure plume follows the original
source so it does not grow with the echo. The two cycle controls are independent;
set both to the same duration and phase to keep opening and flashes synchronized.
New effects are disabled in existing Studies.

**Effects → Text → Timing** controls word/character reveals, receding/breathing
size motion, start/end magnification, cycle, acceleration and held motion FPS.
**Perspective pullback** follows a camera-like depth curve, with a fast initial
retreat that settles as the lettering gets farther away.
Type-on preserves the full phrase's layout. Text timing uses the selected scope:
Whole clip is the default, and section overrides are available. Image effects
keep their own clocks. Scrubbing and export need no playback history.

**Broadcast wear** is a reusable image treatment for text, other generated
objects and video: shifting color fields in shadows, full-frame static
interruptions, rolling static bands, colored polarity reversals, CRT curvature
and corner shading. Adjust each independently or set Mix to zero to bypass.
It uses fresh procedural noise; there are no tiled or embedded reference frames.
Its **Polarity** tab exposes cycle, phase, exposure overlap and field
misregistration. **Before finishing** reverses the source before grain and tape
processing, so inverted frames retain their texture. **Composite fringe**,
width and color controls follow contrast edges on any source. The earlier
final-screen reversal and all new operations' neutral defaults remain available.
**Look → Exposure wash** adds fresh uneven illumination, using Field hue and
color spread. **Signal** offers the original Snow and the new Broken sync
texture, static intensity/color, seeded Random outages and Sync tearing during
interruptions. The existing cycle/duration and rolling band remain available.
**Screen** controls CRT glass, inset and wear, plus highlight-driven colored
halation, radius, hue and threshold. These controls also process imported video;
none require a text source. New operations are off by default in older documents.

Text is a generated object in this stage. Video remains a separate source;
independent text-over-video layers and custom font imports are future work.

### Photocopy and foreground studies

**Effects → Photocopy** processes either generated artwork or imported footage.
Ink threshold/contrast, toner amount/size, halftone coverage/dot size/angle,
frayed edges, cold ink, uneven illumination and exposure pulses are independent
controls. **Print FPS** controls fresh grain and exposure flutter; **Exposure
cycle** controls the repeating dark pass and light/color movement. Set Dark
exposure pulse to zero to remove the dark interval. Grain is generated anew
across the entire canvas, without wrapping a tiled paper image.

**Effects → Subject cutout** is an optional video source stage, before jitter
and image treatments. Foreground detects prominent objects; People provides a
person-specific alternative. **Crowd** also detects human regions and analyzes
them individually, helping smaller figures survive changes in foreground
prominence. It is slower on the first visit to an uncached frame.
**Mask continuity** optionally fills short gaps from the source frames on both
sides; **Continuity reach** sets that distance in seconds. Both neighboring
masks and their colors must agree before a pixel is recovered. This avoids an
accumulating trail and respects source trim boundaries and held motion frames.
Zero continuity retains the original single-frame behavior.
Adjust silhouette density, original-background
detail, mask cutoff, feathering and expansion. Optional projected shadows use
the same mask; Subject base follows its lowest point, while Canvas plane lets
you place the ground manually. Crowded scenes, motion blur and occlusions can
produce imperfect edges; this is per-frame segmentation, not identity tracking
or a hand-painted roto tool.

Detection uses [Apple Vision](https://developer.apple.com/documentation/vision/vngenerateforegroundinstancemaskrequest)
locally on macOS 14 or later, without uploading footage or downloading a model.
The first visit to a frame takes longer; masks are cached under
`~/Library/Caches/Nebula Studio/masks-v1/` (512 MiB budget). Detection always uses
the same 720 px framed input, so preview and export share the mask. Changing
source framing regenerates the affected masks; changing grain or exposure
reuses them. An empty detection produces an empty foreground mask.

The Mac app build compiles and bundles the Swift helper automatically. For
development, run `.venv/bin/python scripts/build_mask_helper.py` with Apple's
command-line developer tools installed. Photocopy works without this helper;
only Subject cutout needs it. Both effects are opt-in. All prior module indices,
seeds, defaults and visual contracts remain unchanged.

The default view is a **composer**: sections below the preview and an **Effects**
inspector. It opens the **Refined signal** study with its original animated recipe.
Choose a study in **Studies**, then press **Load study** to create an editable
copy. The library includes Refined signal, Approved signal, Particle head,
Expand / orbit, Original particles, Ink bloom, Mixed media / two bursts,
Profile / phosphor scan, Profile / signal echoes, Profile / clear silhouette
and Profile / Doryphoros.
Selection alone does not replace the
current composition; loading a study keeps the current canvas format.
The picker shows **Choose a study…** when opening a document, so it does not
misidentify the open composition. Its name appears below the monitor.

**Save as study…** adds the current composition to the Studies library under a
name you choose, without replacing the working document. A study is an
independent snapshot of its source recipe, sections, effects, timing, master
grade and canvas. Each load opens a fresh editable copy and retains the current
output canvas format, just like the built-in studies.

Personal studies live in
`~/Library/Application Support/Nebula Studio/Studies/`. Video studies include a
local copy of their source in the same folder, referenced by a relative path,
so moving the original video does not break the saved study. Copying the whole
study folder to another installation's Studies directory preserves it. Saving
runs in the background and publishes the folder only after the document and
video are complete; cancellation or a failed copy leaves the library intact.
Personal study media is local user data and is not part of the repository or
Mac application bundle. Existing built-in IDs and rendering contracts are
unchanged by the UI rename from Starters to Studies.

The native editors share a terminal-inspired interface: a system-available
monospaced font, dark panels, phosphor-green controls and a violet playhead.
The synth monitor shows the rendered preview dimensions, RGB format and
play/hold state. The theme lives in [`studio_theme.py`](studio_theme.py) and
affects the interface only; saved compositions and exported pixels are unchanged.

Effect controls are grouped by purpose and fully expanded within the selected
Look, Timing, Signal, Screen or Region tab. **Find a control in this tab…**
filters their labels; clear it to restore the complete group list. Numeric
controls show at most two decimal places while retaining saved precision.
Small normalized values use percentages (`0.0007` becomes `0.07%`). Sliders
commit on release, and typed edits commit with Enter or focus change. The
composer reuses its compiled state, and preview requests debounce rapid edits.
Text wording appears at the top of Object; **Apply text** commits the phrase.

- Select **Whole clip** to adjust the entire piece, or click a section to
  adjust it locally. Sections can be added, duplicated, removed, reordered,
  and given different durations under **Arrange**. Set a section's **loops**
  count there to repeat that section's edited event sequence in place; the
  timeline and export use the repeated duration automatically. Each repetition
  restarts the events at the selected section duration, even after rhythm edits.
  Procedural motion/noise and imported footage keep their continuous clocks;
  use **Source → Loop trimmed range** to repeat the source video itself.
- **Effects** exposes luminous forms, rays / Venetian blinds, particle attractors, ghosts / trails,
  signal breakup, signal drift, granular halos, exposure flares, color
  separation, signal interference, bloom, and raster / grain. Select any effect in the library and
  **Apply effect** to add it with a preset. Effects can be combined in any
  section, independently of the section's source phrase. Rays and Venetian
  blinds are two starting settings of the same configurable generator.
- **Applied effects** lists the effects enabled in the current scope, with
  **On** or **Intermittent** badges. Intermittent means the effect is used during
  part of the clip or section. Click a row to inspect its parameters; the
  selected effect is highlighted. **Available effects** opens a separate,
  collapsible catalog of effects that are off here. Selecting an available
  effect opens its inspector; **+ Apply effect** adds it using the chosen preset.
  Both lists use the panel's normal scrolling, with no nested scroll area.
  Bypassed effects appear in Available with a **Bypassed** badge and retain their
  settings. The lists update after edits, section/scope changes and Undo/Redo.
  Selecting another section opens an active effect if the previously inspected
  effect is unused there. Off applies only to the
  inspected effect, not to the section. Authored parameters that vary are shown as ranges. Click a range to
  start a fixed value at its lower bound, then edit it. **↶** restores that
  parameter's recipe or inherited value. Unedited parameters keep animating.
  **Follow recipe** retains the authored enable/disable changes; **On** or
  **Off throughout scope** overrides those changes. **Restore** removes that
  effect's overrides from the current scope.
- **Object** is the common place for the scene's source. It replaces the former
  Geometry tab and opens the controls for the object actually used by the study:
  **Geometric signal** edits the luminous form/ray aperture, **Ink stamps** edits
  the printed silhouette, artwork, dimensions and layout, and **Particle model**
  edits the head/sphere/ring model, pose, size and point density. **Model silhouette**
  projects the bundled head as a fixed solid shape with angle, tilt, scale, framing
  and neck shaping controls. Irrelevant geometry
  controls are hidden. **Motion & timing** opens the shared ink Timing controls;
  **Source controls** (or **Text appearance**) opens the complete Effects inspector.
  Choosing an object type replaces source families in the selected scope while
  keeping treatments, canvas, timeline and durations. Whole-clip replacement also
  resets local source activation overrides, retaining their parameter values.
  Switching back to an authored source follows its original enable/disable
  choreography. **↶** follows study/whole-clip source activation again; object
  parameter edits and embedded artwork survive switching. Undo/Redo, save/open
  and detailed copies preserve the result. Existing combinations made through
  Effects remain editable; Object names additional active source families.
- **Object → Position X / Y** moves the complete source group in output canvas
  pixels. Positive X moves right; positive Y moves down. Zero preserves the
  study's authored placement and movement. Stamps and their split pieces,
  particles during assembly/expansion, geometric sources and attached ghosts,
  halos and glow follow the placement; full-canvas noise and tape processing
  remain across the canvas. Whole-clip position applies to all sections; a
  selected section adds a local offset. **Reset position** clears both offsets
  in that scope. Position survives object-type switches, canvas resizing,
  Undo/Redo, save/open, detailed copies and export. Preview zoom does not change
  its units. Existing per-effect positions remain available in Source controls.
- **Total** beside the playback counter always shows the complete duration,
  calculated from the sum of each section's duration multiplied by its loops
  count. It updates after section edits, loop changes and automatic timing
  changes, including the two-burst study. No separate total duration edit is
  needed.
- Effects use absolute values. Whole-clip settings apply first; section
  settings override them. Fixed effect values take priority over geometric Object controls
  and Finishing. A luminous form's companion ghost and granular halo require
  that form; ghost trails also apply to rays. Exposure flares are independent
  of the timeline's flash/sweep transitions. There is one instance per effect
  family, in the renderer's established order.
- In **Object → Geometric signal**, choose a rectangle, ellipse, circle or regular polygon.
  Width and height scale rectangular/elliptical forms; circles and polygons
  use a diameter measured as a percentage of image height. Polygons have
  3–32 sides. Rotation is available for rectangles, ellipses and polygons.
  The same geometry shapes the luminous source, its echoes and the central
  ray aperture. **Finishing** holds the relative treatment adjustments:
  1× means the original recipe, so different sections can look different at 1×.
- **Original geometry** retains each source state's authored shape. Sections
  default to **From whole clip** and can override it independently. Geometry
  saves with the composition and supports undo/redo. **New take** keeps the
  shape, diameter, height, sides and rotation; the Width macro still varies
  rectangular/elliptical forms unless locked. Circles remain circular.
- **New clip** starts an empty 15-second section. Add forms, rays or particles, then
  combine them with signal effects. In the bundled studies, choose source
  phrases under **Arrange**. Phrases repeat to fill their duration;
  **Rhythm** controls how quickly their internal changes happen.
- **New take** makes a reproducible variation in the current scope. **Keep**
  locks a macro value during variation. Fixed effect values stay fixed.
  **Reset controls** clears the scope's effect overrides and returns it to
  1×, its original geometry and variation; **Undo / Redo** recover composition edits.
- **Save…** keeps effects, arrangement, macros, locks, variations and a snapshot of
  the source recipe together in a versioned composition document. **Open…**
  accepts compositions and existing detailed sequence files.
- **Open detailed copy…** opens the generated events and full parameter editor
  in an independent window. Editing that copy leaves the composition intact.
  Detailed sequences can be brought back into the composer as a single phrase
  with **Use this sequence in composer**.

[`synth_composition.py`](synth_composition.py) compiles the arrangement to the
existing public sequence format. Preview and export therefore use the same
sequence renderer as the approved study. A fixed pixel-hash regression checks
all 375 frames of each study at 96×72 against their earlier renderers;
composition tests cover local edits, deterministic variation and save/reload.
[`synth_effects.py`](synth_effects.py) registers each reusable effect's parameter
paths, activation rules and starting presets. The native inspector is generated
from that registry, and the composition compiler writes ordinary sequence
overrides. Older documents gain an empty effect rack and keep their pixels.
The signal-breakup module is disabled in older presets; its held horizontal
tears and dropouts are deterministic under scrubbing and export.

### Master adjustments and scrolling

The **Master** tab applies **Brightness**, **Contrast** and **Saturation** to the
whole composition, regardless of the selected section. Brightness starts at 0%;
contrast and saturation start at 100%. Saturation at 0% produces black and white.
**Enable master** bypasses the adjustment without losing its values. Use **↶**
to reset one control or **Reset master** to restore all neutral settings.

Master affects the finished image, including backgrounds and transitions, before
Low-res finish enlarges its working raster. Preview and MP4 export use the same
processing. Save/open, Undo/Redo and detailed copies preserve the settings;
the detailed sequence editor also exposes Master. Old documents remain neutral
and retain their exact pixels. Master is independent of section effects and
the relative recipe controls in Finishing.

Closed dropdowns, numeric fields and sliders ignore the mouse wheel and trackpad
so scrolling moves the surrounding panel, even after a control has focus. Open
dropdowns with a click and select an option from their list. Typing, keyboard
arrows, slider dragging and numeric step buttons continue to edit values.

### Canvas formats

The **Canvas** dropdown changes the generated canvas independently of effects,
source recipes and timeline settings. The built-in formats are:

| Format | Canvas |
| --- | --- |
| Original · 5:4 | 720 × 576 |
| Stories / Reels · 9:16 | 1080 × 1920 |
| Portrait feed · 4:5 | 1080 × 1350 |
| Square · 1:1 | 1080 × 1080 |
| Portrait · 3:4 | 1080 × 1440 |
| Landscape feed · 1.91:1 | 1080 × 566 |
| Widescreen · 16:9 | 1920 × 1080 |

Changing format preserves the artwork's original pixel dimensions, proportions
and center, like resizing a canvas in an image editor. Smaller canvases crop the
view; larger ones reveal more space. Geometry, particles, ink figures and frame
jitter keep the same reference dimensions. Noise, raster, tape damage, fields
and transitions render across the entire new canvas.

**Fit subject** is optional: it uniformly scales the artwork's reference canvas
to fit inside the selected output. Both axes always use the same scale. Changing
format defaults to preserving the original size; neither mode edits authored
geometry, motion or effect parameters.

Canvas settings save in compositions, detailed sequences and standalone presets.
Composer Undo/Redo includes canvas changes. Returning to the original artwork
dimensions restores its framing. Earlier documents keep their saved framing and output until
the canvas is edited. Studies are independent copies; loading one retains the
selected output format and uses that study's own artwork reference.

**Preview quality** affects only the monitor (360 px, 720 px or full canvas).
**Export MP4** always uses the document's full dimensions, shown beside Canvas,
even with a fast preview selected. The export snapshots the canvas and scene so
subsequent edits do not change an in-progress render. Custom dimensions in loaded
documents are retained. The new format/size helpers live in `synth_canvas.py` and
the built-in registry lives in `synth_starters.py`; `synth_studies.py` combines it with personal studies.

The monitor reports **Preview: measured / target FPS** separately from export
FPS. Live playback follows elapsed time, skipping preview frames when rendering
cannot keep up. **Prepare playback** renders the full loop at the chosen preview
quality into a 192 MB memory buffer; then **Play cached preview** plays those
frames without re-rendering. Preparation shows progress, can be cancelled, and
does not block editing. Completed frames are also reused when scrubbing.
Edits, quality changes and source bypass clear the buffer and reject stale jobs.
If a full loop exceeds the budget, choose 360 px or shorten the timeline.
Preview remains silent and exports still render every frame independently.
During MP4 export, the monitor shows a frame-based progress bar with percentage
and current/total frame count; completion, cancellation and errors remain visible
after the worker finishes.
Subject cutout also caches held-frame masks and continuity results in 32 MB per
video reader, keyed by source identity, framing, trim, detection and retention
settings. Treatment-only edits can reuse those masks without changing pixels.

**View zoom** below the monitor changes only the view. Choose **Fit**, **100%**,
enter a percentage, or use **− / +**. Drag to pan a zoomed image, double-click to
fit, or use Ctrl/⌘ + wheel to zoom around the pointer. Zoom does not change
preview quality, export resolution or the composition.

Drag the divider between the monitor and inspector to adjust the effects
column's width. The app remembers this split, view zoom, window position, size
and fullscreen/maximized state. On first launch it opens fullscreen; the header's
**Full screen / Exit full screen** button switches modes. Detailed-copy windows keep
their own temporary layout without overwriting the main workspace preferences.

**Effects → Low-res finish → 360 px preview feel → + Apply effect** keeps
the texture of the 360 px preview in a full-size export. Choose the whole-clip
scope to apply it throughout, or select a section for a local treatment.
**Working resolution** sets the longest edge of the internal raster; the saved
canvas supplies its proportions. **Enlargement → Soft** smoothly enlarges the
grain and softened edges, while **Crisp pixels** preserves hard pixel edges.
The 180 px, 720 px and crisp 240 px looks provide other starting points.

This renders sources, grain, backgrounds and sequence transitions at the chosen
resolution before scaling the finished frame. Preview quality changes only the
monitor size when the effect is on; the artistic raster stays the same in the
preview and export. Export MP4 still writes the full canvas dimensions. The
effect saves with the document and supports section overrides, Undo/Redo and
detailed editing. It is off in existing studies; disable it to restore native
rendering. Working resolution is capped at the saved canvas size.

### Printed mixed media

**Effects → Ink bloom → Timing** exposes the gesture as four durations in
seconds: **Unfold**, **Stay unfolded**, **Fold**, and **Stay folded**. Timing is
**shared across all sections**, including when a section is selected. The first
edit establishes one complete timing profile and continuous clock; changing
sections then shows the same values. Shape, inks and other appearance effects
keep their existing section controls. Use **↶** to restore a timing value from
the base recipe, or **Restore recipe timing** to return the original motion.
Save/open, Undo/Redo and detailed copies retain the settings.

Sections that already span complete ink cycles resize together when timing
changes, retaining their cycle counts. This keeps the second variation between
gestures. Boundaries round cumulatively to export frames without adding drift.
Manually arranged sections that do not span whole cycles keep their lengths;
the shared motion clock continues through their boundaries. Old saved timing
overrides are consolidated: whole-clip timing wins, otherwise the first section
with custom timing supplies the common profile. The embedded source is retained.

**Gesture speed** scales this motion independently: 2× runs twice as fast, .5×
runs at half speed, and 0 freezes it. Durations are measured at 1×; the inspector
shows the resulting loop length at the current speed. The turn is retimed with
the opening and closing so the same edge-on views survive a fast unfold. The
figure can keep turning during a fully open or closed hold. Stay folded is the
total rest between gestures, split around the loop boundary in the recipe's
original proportion. Zero-duration stages are instantaneous; all four at zero
hold the closed pose.

**Motion FPS** controls how often the geometry updates, independently of
**Gesture speed**: at .1× and 15 Motion FPS the figure still gets 15 poses per
second, with smaller movement between them. For smoother motion, raise Motion
FPS and the clip frame rate in Arrange together (for example, both to 30 fps).
Lower Motion FPS deliberately retains the mixed-media holds. **Frame jitter → Jitter
FPS** independently controls how often the tiny positional shakes change; 6–8
FPS gives longer holds than 15 FPS. Print/background noise also keeps its own
clock. **Arrange** controls custom section and clip lengths. **Timing**
includes cycle phase and automatic/manual cycling; the original percentage
settings remain in the detailed editor. Untouched recipes keep their approved
frames until a shared timing edit is made.

**Studies → Ink bloom** creates a 3.53-second, 15 fps study from one editable
section. Select **Canvas → Square** for its reference framing. Seven ragged
cyan, magenta, yellow and white impressions unfold into a rotating cluster,
pass through edge-on views, and fold back into a compact stamp. The shapes and
paper are generated procedurally; no reference footage or downloaded textures
are needed by the app.

Two independent effects are available in every composition:

- **Ink bloom:** stamp count, size, spread, point count/depth, shape irregularity,
  ink palette and split colors. Grouped Look and Timing controls expose opening/closing timing,
  cycle phase, signed turns, tumble, tilt, individual fanning, cluster depth,
  closed-stack spacing, middle folding, reverse-side ink, perspective and position. **Automatic cycle = 0** makes
  **Opening** a manual control. Motion FPS holds the geometry independently of
  export FPS; rates are measured at global speed 1.
- **Print surface:** paper and ink grain, ink wear, frayed edges, held scan
  registration, rotation jitter, persistent fibers, broad paper mottling, fresh
  texture boil, dust and scan softness. It treats the combined image, so it can
  also be applied to the head, rays and other sources. **Mix = 0** is an exact
  bypass. Scan FPS sets its own cadence at global speed 1.

Ink bloom now uses **Print surface → Background → Frame noise**: a fresh
full-canvas grain field and new density patches on every held scan frame, with
no translated texture or wrapping. Background noise, Noise size, Noise clumping
and Background tone are independent of the figure's ink treatment. The source
and its softened edges are protected while the surrounding background changes.
The noise remains deterministic when scrubbing or exporting. **Original paper**
retains the previous moving-sheet treatment and is the default for older saved
documents. To update an existing clip, change only Background to Frame noise;
the Chaotic background preset also provides a starting point for new effects.

**Ink bloom → Stamp shape** replaces the figure with a square, circle, triangle,
regular polygon or imported artwork. The original burst remains the default.
The animation uses a stack of flat stamps: one central impression and surrounding
copies overlap, unfold in 3D, turn and gather again. Replacing the silhouette
keeps that motion, the selected ink palette and the independent print background.
Shape width, height, rotation and polygon side count are in the Look tab's shape controls.

Use **Custom artwork → Import…** for a transparent PNG cutout or a contrasting
image (PNG, WebP, TIFF, JPEG or BMP). Transparency supplies the silhouette; for
opaque artwork, choose light areas on dark or dark areas on light. Holes and
partial transparency are retained. Import selects Custom artwork automatically.
The figure is recolored with Ink palette; source RGB colors are not retained.
Empty margins are cropped, proportions are preserved, and masks over 2048 pixels
are reduced on import. The processed silhouette is embedded in the document, so
save/open, detailed copies and export work after moving the original file.
Switching to a built-in shape keeps the artwork available. Imports and edits
support Undo/Redo and section overrides; ↶ restores the inherited artwork.

**Frame jitter** is a reusable effect for the ink figures, particle head and
other generated sources. Apply **Hand-positioned paper**, **Subtle scan** or
**Loose cut-paper**, then set Horizontal/Vertical jitter, Rotation jitter,
Scale jitter, Jitter FPS and Jitter strength. Position values are pixels at a
720-pixel short edge and scale with the preview/export canvas. Each held frame
gets a bounded pose around the authored position; the figure never drifts away
over time. The advanced Jitter seed changes its movement independently of the
source and print textures. Jitter strength = 0 bypasses exactly; Jitter FPS = 0
freezes the pose. The renderer places this effect before bloom, raster and print
finishing, so fresh print background noise retains its own frame pattern.

**Studies → Mixed media / two bursts · 7s** opens a 106-frame, 15 fps composition
with two editable sections and Frame jitter enabled. The second gesture opens
wider, fans out, adds depth/tilt and turns in the opposite direction. A short
parameter transition starts while the first gesture is closed. Replace its
Stamp shape or import artwork to reuse the full motion. The original Ink bloom
study and saved clips retain their previous output.

The shorter canvas edge controls stamp size, preserving proportions when
switching formats. Paper covers the entire canvas. Effect overrides support
save/open, Undo/Redo, section scope, independent study copies and detailed
editing. Width, Instability and Texture finishing controls also affect the new
source/treatment; Cycle seconds and opening/closing controls set its gesture.
Seeded identities make scrubbing and export deterministic. The original signal
and particle studies remain unchanged. Implementation: `synth_print.py`.

### Particle attractors

**Studies → Profile / phosphor scan · 4s** creates a 61-frame study at 15 fps,
with a fixed left-facing human profile and four editable sections: Green lock,
Overload, Red hold and Lower scan tear. It uses the existing CC0 head mesh;
no frames or textures from a reference GIF are bundled. Low-res finish renders
at 480 px before enlarging to the saved 960×540 canvas.

- **Object → Model silhouette** controls the head model, uniform scale, angle,
  tilt, roll, framing, neck extension/fullness and contour softness. The mesh has no
  automatic rotation. Shared Object X/Y places the complete source group.
- **Effects → Edge phosphor** turns a source into a dark silhouette with a
  colored backlight and contour echoes. Edit backlight hue/saturation/strength,
  grain, reach, contour width/glow, fringe color/gap, lower fade and silhouette
  fill. Light side selects a left- or right-facing contour; Source threshold
  controls the source mask. Phosphor FPS sets the held texture cadence.
  **More controls → Canvas coverage → Extend to canvas** continues the backlight
  above and below the object when resizing reveals more space. The model and
  its contour keep their size and proportions.
  **Region → Profile preset → Neck dissolve** fades the model's bright neck edges and
  softens the silhouette into the backlight below the jaw. It follows model
  framing, scale, roll and Object X/Y. Both profile studies enable it; set it
  to 0 for the previous outline. Saved clips keep their setting (0 if absent).
  In **Region**, choose **Object** for a reusable fade attached to the source,
  or **Canvas** for a fixed viewport region. Adjust Fade strength, Fade start,
  Fade width, Fade direction and Light blending. More controls exposes the
  object anchor, region X/Y and linear/smooth curve. Object units follow the
  source's scale; canvas units are half its shortest edge. This blends contour,
  fringe, echoes, fill and backlight at their original stages, before final
  texture. Missing object anchors are identified in the inspector.
- **Effects → Scan drag** stretches the source's bright colors into scanlines.
  Fine streak density/reach, overload strength/position/thickness/exposure,
  tracking tear count/height, irregular row groups, overload bloom, chroma slip, grain,
  softness, direction and fault FPS are independent. Recording width controls
  black side margins in the original canvas; set it to 1 for a full-width signal.
  **More controls → Canvas coverage → Extend to canvas** lets streaks and
  overloads reach the resized canvas edges instead of clipping at the original
  recording width. Choose **Artwork bounds** in either effect to retain its
  former framing. Both effects default to extending into the newly revealed
  canvas, including in saved profiles. Native landscape renders stay unchanged.
  A blank image never
  gains luminous bars. Mix = 0 bypasses either treatment exactly.
- **Effects → Signal background** fills the deepest blacks, including the
  silhouette and recording margins, with Refined signal's faint green tint,
  fine grain and horizontal noise. Background level, Fine grain and Horizontal
  grain control its presence; Green tint, Chroma noise and Scanline depth shape
  its color and texture. Shadow reach limits it to dark pixels so bright
  contours remain untouched. Background FPS controls its held cadence (0 freezes
  it); Mix or Background level = 0 restores the original black. The texture
  covers the whole canvas and stays in place when the object moves.

Both treatments can be applied to other sources through Effects. The study
embeds its settings, keeps the same head pose throughout its sections, and
supports whole-clip/section edits, reset, Undo/Redo, save/open, detailed copies,
canvas reframing and MP4 export. Other studies keep these effects disabled
and retain their original rendering.

New profile studies enable Signal background across all four sections. To
update a saved profile, choose Whole clip, then add Signal background from
Available effects. Saved compositions and other studies retain their prior look.

**Studies → Profile / signal echoes · 8s** adds a separate 120-frame variation
at 15 fps. Six sections progress through Green lock, Overload, Red / falling scan,
Violet echoes, Flare / signal rupture and Green return. The second half brings
in **Ghosts / trails**, **Exposure flare** and **Signal drift**, with a brief
violet pause and a return to the initial green palette. All six sections keep the
same fixed head pose and Signal background settings. Edit each effect at Whole
clip or section scope; changing section durations updates the total. The
four-second study and saved projects remain unchanged.

**Studies → Profile / clear silhouette · 8s** keeps that choreography in a
separate variation, with a slightly larger profile, tighter glow/fringe and
quieter scan streaks between overloads. **Object → Facial definition** emphasizes
the nose, lips and chin before projection; 0 preserves the original geometry.
The study uses an explicit object region for the neck blend. Its mesh assets,
the original Profile / signal echoes and Refined signal are unchanged.

**Studies → Profile / Doryphoros · 8s** uses a CC0 museum scan of the classical
Doryphoros head with the clear silhouette variation's six-section treatment.
Facial definition and neck fullness start at zero to retain the scan's profile;
the reusable directional region blends the neck into the signal. Select the mesh
independently through **Object → Head model → Doryphoros**, or use it as a particle
target through **Object → Attractor → Doryphoros** in any particle study. Pose,
scale, Object X/Y, canvas framing and treatments remain independent controls.
The mesh has 32,000 triangles and needs no additional runtime dependency. Source,
CC0 license and reproducible preparation are recorded in
[`assets/models/README.md`](assets/models/README.md). Previous studies and models
keep their original settings.

The original nine study recipes and preset defaults are frozen in
`presets/compat-v1.json`. Unversioned documents use rendering contract 1; new
study copies use contract 2, whose generic phosphor treatment matches the
captured originals. The original phosphor code remains available for contract 1.
These versions describe algorithms, independently of JSON schema versions.
See `tests/fixtures/synth-baseline-v1.json` for 99 cases / 3,385 raw-frame checks
and `requirements-render-v1.txt` for the recorded NumPy/Pillow versions. Future
changes to shared algorithms still need compatibility implementations and visual
regression checks; an engine version field alone does not preserve old pixels.

**Studies → Particle head** opens the **Particle signal** study: dots rush into an
anatomical head, rebound and dissolve toward a thin luminous band. Three sections
(Charge & gather, Signal storm, Release & return) combine the continuous particle
motion with 11 signal-treatment cues. **Original particles** retains the first
one-section study and its original pixels.
**Expand / orbit** opens a 15-second variation with exactly two expansions,
arranged as two sections. The assembled head turns at 18°/s, expands quickly with
a narrow velocity peak, revolves as a broad cloud at 24°/s, then gathers again.
A shared centered axis keeps the cloud from circling an offset pivot. The head
inherits the cloud’s accumulated rotation on return, so reassembly keeps turning
forward instead of unwinding toward an earlier angle. The neck
fades into sparse points above the mesh edge. The portrait uses smooth
facial geometry, eye surfaces and depth occlusion to suppress the mouth interior
and far side. A restrained violet/white palette keeps the earlier color direction.
Tape faults replace the added bars: tracking slips, scanline loss, color lag and
bleed deform the existing image. The strongest faults follow the main outward
move so it stays visible. Existing saved orbit clips retain their earlier motion
and colors; Particle head and Original particles also retain their pixels.
The default startup study and **Refined signal / Approved signal** remain unchanged.
You can also apply **Particle attractor** from Effects to any composition.

- **Motion → Surges** adds **Acceleration**, **Arrival disorder** and
  **Overshoot**. Groups hesitate, arrive on curved paths at different times and
  rebound before settling. The cycle's timing drifts continuously. **Gentle**
  retains the original motion; older saved presets default to Gentle.
- **Motion → Impulse** separates the movement from the hold. **Expansion seconds**
  and **Gather seconds** set the outward and inward durations, while **Motion peak**
  shapes the speed curve: 0 is linear; higher values ease into a narrow velocity
  peak and ease out again. The example uses a .75-second expansion, a 1-second
  return and a .8 peak. **Cycle seconds** controls repetition independently.
  Expansion/gather durations cap at 25%/20% of the cycle to leave room for holds.
  Arrival disorder adds a small stagger without changing the number of cycles.
  Orbit speed and expansion threshold remain under **More controls**.
- **Assembly** sets how tightly particles follow the invisible surface.
  **Assembly cycle** controls automatic gathering and release; set it to **0**
  to hold Assembly at a fixed value. **Cycle seconds** sets the period at global
  speed 1, and **Cycle phase** changes the starting point. This motion lives in
  the effect; it does not require extra timeline states. The inspector displays
  the cycle's settings, not its instantaneous computed assembly value.
- **Release → Expand / orbit** chooses the new outward motion. **Dispersion**
  sets its spread, **Orbit degrees / sec** sets cloud rotation (negative reverses
  it), and **Orbit after expansion** delays spin-up until the field opens out.
  The example uses 24°/s and a 70% threshold. Orbit slows as particles gather;
  **Turn degrees / sec** separately rotates the entire target and field.
  **Cloud / band** restores the earlier release and its **Collapse to band**
  control. Collapse is ignored in Expand / orbit, which has no downward pull
  or funnel taper. Release and orbit settings can also be overridden per section.
- **Particle count**, **Dot size**, **Dispersion** and **Turbulence** set density,
  texture and the released field. **More controls** includes collapse toward a
  horizontal band, rotation, tilt, scale, position, perspective, surface relief,
  see-through depth, spectral color, shimmer and scan registration.
- **Human head** uses an anatomical head/neck mesh derived from MakeHuman's
  CC0 base asset, sampled uniformly by surface area. Geometry and interpolated
  normals provide the facial detail; the solid mesh is never drawn. The 94 KB
  asset is bundled for offline use. [Provenance and license](assets/models/README.md)
  include its pinned source and extraction script. **Stylized head**, **Sphere**
  and **Ring** retain their earlier procedural surfaces. Arbitrary mesh import
  and physical collision/gravity simulation are not included.
- **Portrait head** adds the source's eye surfaces and a smooth subdivision pass.
  The separate 454 KB mesh keeps the earlier Human head asset unchanged.
  **Surface occlusion** under More controls hides deeper points behind the
  assembled face using a fixed proxy depth grid. It fades away as particles
  disperse; only points are rendered. Older documents default to zero occlusion.
- **Turn timing → Assembled only** eases the head turn to a hold during release,
  keeping **Turn degrees / sec** independent of **Orbit degrees / sec**.
  **Rotation axis → Centered** aligns both volumes to a common vertical pivot;
  its reference population is fixed, so changing Particle count retains identities.
  **Neck feather** softens the lower edge of head targets and restores those dots
  during expansion. These controls are under Particle attractor → More controls;
  old documents keep continuous turning, the original origin and no feather.
- **Return rotation → Carry orbit** gives the head and cloud one accumulated
  orientation. The head reforms at the angle reached by the orbit, preventing
  a backward turn during gathering. Particle positions and surface lighting
  turn together; expansion timing and easing remain independent. Older documents
  retain **Original head angle** unless this control is changed.
- **Tape damage** processes the recorded image after its other treatments.
  Tracking slip and line jitter displace existing pixels; Dropouts remove short
  stretches of scanline. Chroma delay and Color bleed lag/smear the source's own
  color, and Head-switch error distorts the bottom edge. Fault changes / sec
  controls its held cadence; 0 freezes it. Mix 0 bypasses exactly. The new study
  has no active rays, slabs or flare generators. Tape damage is off in old presets.
- Combine particles with bloom, raster / grain, color separation, trails or
  signal breakup. The particle source runs before those treatments. Parameters
  support whole-clip/local overrides, bypass, restore, undo/redo and save/open.
  **Object → Particle model** controls the model, scale, pose and point density.
  **More object controls** opens its complete inspector, including head turn,
  assembly, expansion and orbit controls.
- **Signal interference** is a separate reusable effect: moving chromatic bands,
  uneven exposure and bent vertical scan strings. Its speed, bending, density,
  contrast, chroma and mix are editable. The Particle signal study also uses the existing
  warp, separation, trails, bloom, raster, brief exposure crests and tracking breaks.
  Released brightness dims particles between bursts. Neither reference video
  pixels nor external services are used by the renderer.

[`synth_particles.py`](synth_particles.py) keeps seeded point identities and
evaluates continuous paths directly from time. Scrubbing, held treatment frames
and export therefore agree without a simulation warmup. The new module is off
in all existing presets. Regression tests retain every saved pixel hash for both
375-frame studies and selected frames of both earlier particle studies. Higher
particle counts cost more CPU time. Save/export dialogs suggest the current
composition's name under Documents/Movies, avoiding Finder's read-only root
working directory.

The refined study adds granular halos and ghosts, edge flutter, short horizontal
noise streaks, blue-violet falloff in dim forms, colored ray tails and uneven
exposure sweeps. **Texture**, **Instability**, **Magenta** and **Flares** control
these treatments in the current scope; **Brightness** also affects ray cores.
The detailed editor exposes each new parameter independently. New renderer
parameters default to neutral values so the approved study remains unchanged.
Previously saved compositions retain their source snapshots; non-neutral
Brightness settings now also scale ray intensity.

The approved recipe is [`presets/composite-study-15s.json`](presets/composite-study-15s.json);
the new treatment is [`presets/composite-signal-refined-15s.json`](presets/composite-signal-refined-15s.json).
It includes 323 frame-timed cues at 25 fps: rapid ray-count changes, asymmetric
exposure sweeps, alternating filled/fragmented blocks, a dim violet passage,
and a noisy final return. It is a procedural interpretation; signal feedback
and the exact textures of the hardware reference are not reproduced exactly.
The reference video is not a rendering input and is not distributed here.

In the detailed editor, selecting a cue scrubs to its time. **Duplicate state** creates an independent
copy and assigns it to that cue. **Generate variation** changes the selected
state and honors its parameter locks. The **Signal flare** module controls
exposure, position, spread, reach, and fringe; slab controls include split
magenta/white fill, per-frame registration, ghost grain, and a localized signal
cloud. **Signal softness** softens the image before the final raster grain.
These controls also work in standalone presets.

## Experimenting

1. **Open clip…** loads a local video. The source is read-only. The initial loop is two seconds at the existing default treatment rate of 12 fps.
2. Adjust the controls on the right. **Lo / Hi** values define temporal ranges, not separate still variants. Translation, blur and channel offset are expressed in source pixels. Setting one bound across the other moves the other bound with it.
3. **Enabled** bypasses a stage. The **View** selector shows the source or the output after print, scan, motion or grade. Export always renders the final enabled treatment, regardless of the inspection view.
4. Scrub the timeline, use **Set here** for the loop start, and choose one, two or three seconds. **Play loop** (or Space) plays the prepared frames and holds while buffering. Lower **Frames per second** gives longer frame holds in preview and export.
5. **Capture A** stores the current settings. Edit B, enable **Compare A / B**, and drag the divider. Both sides follow the same clip and exact source frame as you scrub; A retains its seed and settings. Capture again to replace A. Opening a different clip, changing fps, loading a preset or resetting clears A.
6. **Fast** and **Detailed** select maximum proxy dimensions of 480 and 720 pixels. **Full-size still** renders the current frame at original resolution. It pauses playback; Play returns to the proxy loop. The viewer fits the frame to the window.
7. **Load preset…** accepts existing flat JSON presets and project `tune_params.json`. **Save preset…** defaults to `~/.nebula_pipeline/presets`. Settings are saved explicitly, not automatically. Stage bypass is stored under `_stages`; the legacy `grade` key remains authoritative for grade enablement.
8. **Export MP4…** exports either the loop or the entire clip at full source resolution and the chosen fps. It snapshots the current B settings when started, so you may keep experimenting during export. Cancel stops the job; closing the app also cancels background work. The destination is replaced only when encoding succeeds, and the source path cannot be used as the destination.

## Rendering contract

All processing follows **print → scan → wobble → grade**. `engine.render_frame` is used by the desktop preview/export and the legacy analog sequence processor. The legacy grading pass uses the same `grade_frame` function. The TUI's external preview now renders its selected frame rather than a low/mid/high sheet.

Randomness is keyed by seed, effect name and absolute output-frame index. Parameter changes, stage bypass and scrub order do not consume a shared random stream. Motion, rotation, paper, channel direction, bands, grain and dust have separate streams. Smooth temporal variation uses deterministic interpolated knots every eight treatment frames; it is independent of clip length. Existing preset values remain usable, but historical seeded output changes because the old global random walk has been replaced. A missing/null seed resolves to 42.

Preview and export use the same FFmpeg fps grid, including selected-range exports. The full-size pixels **before encoding** match for the same source/frame/settings. MP4 export uses H.264 CRF 18 with 4:2:0 chroma, which is lossy; odd source dimensions are padded by up to one pixel for encoding. Export is silent, as in the existing pipeline.

Proxy blur, translation, channel offset, bloom and paper scale follow image scale. Grain and row noise use reduced variance, and subpixel scanlines converge toward average darkness. Fine dust/noise locations and subpixel shifts are approximations at proxy resolution; use Full-size still to judge fine texture. No real-time full-resolution promise is made.

## Responsiveness and limits

A 100 ms debounce coalesces edits. The preview worker prioritizes the selected frame, then prepares the loop. New requests cancel obsolete FFmpeg work; generation IDs discard late results and errors. Source and rendered-frame caches have 64 MiB and 128 MiB budgets, and the displayed loop has a 128 MiB budget. A/B and high-fps loops automatically use smaller proxies to fit. Export uses a separate worker and an atomic temporary output.

For accurate variable-rate seeking, decoding starts from the beginning of the clip before selecting the requested frame. Seeking late in a long clip can therefore take longer. CPU rendering, silent MP4 output, one clip at a time, fixed stage order, and no audio playback are intentional first-version limits. Frame-count estimates depend on container duration; malformed duration metadata may require choosing an earlier loop position. There is no installer, node graph or multi-clip editing in this milestone. Undo/redo is available in the synth composer; the detailed editor and input-clip workflow do not yet have undo history.

## Validation

```sh
.venv/bin/python -m pip install pytest
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
QT_QPA_PLATFORM=offscreen .venv/bin/python tests/measure_preview.py /path/to/reference.mp4
```

The checks cover deterministic scrubbing, global RNG isolation, effect-stream isolation, pixel parity between legacy processing and preview, source decode-grid parity, absolute frame indices during range export, source/destination protection, cancellation, actual Qt controls and playback, same-frame A/B after rapid edits and bypass, stale-result rejection, preset round trips, full-size preview and GUI export.

Representative local measurements using the read-only `ref5.mp4` reference (720 × 1280, 29.56 s), default settings, 270 × 480 proxy, 24-frame / two-second loop:

| Action | Current frame | Loop prepared |
|---|---:|---:|
| Cold clip open, including probe/debounce/decode | 275 ms | 734 ms |
| Blur edit with source cache | 124 ms | 518 ms |
| Rapid edits + scrub + A/B with print bypass | 150 ms | 849 ms |
| Full-size A/B still | 283 ms | One still |

These are individual local observations, not throughput guarantees. The measurement script writes `.validation/timings.json`, a Qt window capture at `.validation/studio.png`, and a QA preset. Reference clips are never modified.

The existing `nebula.py`, `_pipeline.py`, `analog_wobble.py`, `grade.py`, `assemble.py` and generation entry points remain available. Desktop dependencies are additive in `requirements-desktop.txt`.
