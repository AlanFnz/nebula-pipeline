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
inspector. It opens the **Refined 15s** study with its original animated recipe.
**Approved 15s** reloads the earlier study with its original recipe and pixels.

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
- Each effect shows its own parameters and whether it is active, intermittent
  or off. **Used in this section** lists the active effects as shortcuts to
  their controls. Selecting another section opens an active effect if the
  previously inspected effect is unused there. Off applies only to the
  inspected effect, not to the section. Authored parameters that vary are shown as ranges. Click a range to
  start a fixed value at its lower bound, then edit it. **↶** restores that
  parameter's recipe or inherited value. Unedited parameters keep animating.
  **Follow recipe** retains the authored enable/disable changes; **On** or
  **Off throughout scope** overrides those changes. **Restore** removes that
  effect's overrides from the current scope.
- Effects use absolute values. Whole-clip settings apply first; section
  settings override them. Fixed effect values take priority over Geometry
  and Finishing. A luminous form's companion ghost and granular halo require
  that form; ghost trails also apply to rays. Exposure flares are independent
  of the timeline's flash/sweep transitions. There is one instance per effect
  family, in the renderer's established order.
- In **Geometry**, choose a rectangle, ellipse, circle or regular polygon.
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

### Particle attractors

**Particle head 15s** opens the new **Particle signal** study: dots rush into an
anatomical head, rebound and dissolve toward a thin luminous band. Three sections
(Charge & gather, Signal storm, Release & return) combine the continuous particle
motion with 11 signal-treatment cues. **Original particles** retains the first
one-section study and its original pixels.
**Expand / orbit** opens a separate 15-second variation with a 3.8-second cycle
(about 21% faster than the 4.6-second signal study). Dots expand in all directions
into a broad volume, then revolve slowly around the vertical axis. It keeps the
same anatomical target and signal treatments. Both earlier examples are retained.
The default startup study and **Refined 15s / Approved 15s** remain unchanged.
You can also apply **Particle attractor** from Effects to any composition.

- **Motion → Surges** adds **Acceleration**, **Arrival disorder** and
  **Overshoot**. Groups hesitate, arrive on curved paths at different times and
  rebound before settling. The cycle's timing drifts continuously. **Gentle**
  retains the original motion; older saved presets default to Gentle.
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
- Combine particles with bloom, raster / grain, color separation, trails or
  signal breakup. The particle source runs before those treatments. Parameters
  support whole-clip/local overrides, bypass, restore, undo/redo and save/open.
  Its own **Scale**, **Head turn** and **Tilt** control the 3D target; the Geometry
  tab still controls luminous forms and ray apertures.
- **Signal interference** is a separate reusable effect: moving chromatic bands,
  uneven exposure and bent vertical scan strings. Its speed, bending, density,
  contrast, chroma and mix are editable. The new study also uses the existing
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
