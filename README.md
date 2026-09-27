# Nebula Studio

A native Python + PySide6 desktop app for experimenting with the existing digital print, scan, motion and grading effects. Open a clip, adjust its treatment, scrub, compare versions, and play a short loop inside the app.

The project version comes from [`_version.py`](_version.py); run `python studio.py --version` to display it. See [versioning](VERSIONING.md) and the [changelog](CHANGELOG.md) for milestone history and compatibility notes.

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

This first synthesis pass is source-free. Input-video modulation is reserved
for the next phase; the existing clip workflow remains available from the same
`studio.py` entry point.

The default view is a **composer**: sections below the preview and an **Effects**
inspector. It opens the **Refined signal** study with its original animated recipe.
Choose a study in **Starters**, then press **Load starter** to create an editable
copy. The library includes Refined signal, Approved signal, Particle head,
Expand / orbit, Original particles, Ink bloom and Mixed media / two bursts. Selection alone does not replace the
current composition; loading a starter keeps the current canvas format.

The native editors share a terminal-inspired interface: a system-available
monospaced font, dark panels, phosphor-green controls and a violet playhead.
The synth monitor shows the rendered preview dimensions, RGB format and
play/hold state. The theme lives in [`studio_theme.py`](studio_theme.py) and
affects the interface only; saved compositions and exported pixels are unchanged.

- Select **Whole clip** to adjust the entire piece, or click a section to
  adjust it locally. Sections can be added, duplicated, removed, reordered,
  and given different durations under **Arrange**. Their internal events are
  generated for you.
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
  Geometry tab and opens the controls for the object actually used by the starter:
  **Geometric signal** edits the luminous form/ray aperture, **Ink stamps** edits
  the printed silhouette, artwork, dimensions and layout, and **Particle model**
  edits the head/sphere/ring model, pose, size and point density. Irrelevant geometry
  controls are hidden. **Motion & timing** opens the shared ink Timing controls;
  **More object controls** opens the source's complete Effects inspector.
  Choosing an object type replaces source families in the selected scope while
  keeping treatments, canvas, timeline and durations. Whole-clip replacement also
  resets local source activation overrides, retaining their parameter values.
  Switching back to an authored source follows its original enable/disable
  choreography. **↶** follows starter/whole-clip source activation again; object
  parameter edits and embedded artwork survive switching. Undo/Redo, save/open
  and detailed copies preserve the result. Existing combinations made through
  Effects remain editable; Object names additional active source families.
- **Object → Position X / Y** moves the complete source group in output canvas
  pixels. Positive X moves right; positive Y moves down. Zero preserves the
  starter's authored placement and movement. Stamps and their split pieces,
  particles during assembly/expansion, geometric sources and attached ghosts,
  halos and glow follow the placement; full-canvas noise and tape processing
  remain across the canvas. Whole-clip position applies to all sections; a
  selected section adds a local offset. **Reset position** clears both offsets
  in that scope. Position survives object-type switches, canvas resizing,
  Undo/Redo, save/open, detailed copies and export. Preview zoom does not change
  its units. Existing per-effect positions remain available in More object controls.
- **Total** beside the playback counter always shows the complete duration,
  calculated from the sum of the sections. It updates after section edits and
  automatic timing changes, including the two-burst starter. No separate total
  duration edit is needed.
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
the canvas is edited. Starters are independent copies; loading one retains the
selected output format and uses that starter's own artwork reference.

**Preview quality** affects only the monitor (360 px, 720 px or full canvas).
**Export MP4** always uses the document's full dimensions, shown beside Canvas,
even with a fast preview selected. The export snapshots the canvas and scene so
subsequent edits do not change an in-progress render. Custom dimensions in loaded
documents are retained. The new format/size helpers live in `synth_canvas.py` and
the starter registry lives in `synth_starters.py`.

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
clock. **Arrange** controls custom section and clip lengths. **More controls**
exposes cycle phase and automatic/manual cycling; the original percentage
settings remain in the detailed editor. Untouched recipes keep their approved
frames until a shared timing edit is made.

**Starters → Ink bloom** creates a 3.53-second, 15 fps study from one editable
section. Select **Canvas → Square** for its reference framing. Seven ragged
cyan, magenta, yellow and white impressions unfold into a rotating cluster,
pass through edge-on views, and fold back into a compact stamp. The shapes and
paper are generated procedurally; no reference footage or downloaded textures
are needed by the app.

Two independent effects are available in every composition:

- **Ink bloom:** stamp count, size, spread, point count/depth, shape irregularity,
  ink palette and split colors. More controls exposes opening/closing timing,
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
Shape width, height, rotation and polygon side count are under More controls.

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

**Starters → Mixed media / two bursts · 7s** opens a 106-frame, 15 fps composition
with two editable sections and Frame jitter enabled. The second gesture opens
wider, fans out, adds depth/tilt and turns in the opposite direction. A short
parameter transition starts while the first gesture is closed. Replace its
Stamp shape or import artwork to reuse the full motion. The original Ink bloom
starter and saved clips retain their previous output.

The shorter canvas edge controls stamp size, preserving proportions when
switching formats. Paper covers the entire canvas. Effect overrides support
save/open, Undo/Redo, section scope, independent starter copies and detailed
editing. Width, Instability and Texture finishing controls also affect the new
source/treatment; Cycle seconds and opening/closing controls set its gesture.
Seeded identities make scrubbing and export deterministic. The original signal
and particle starters remain unchanged. Implementation: `synth_print.py`.

### Particle attractors

**Starters → Particle head** opens the **Particle signal** study: dots rush into an
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
