# Nebula Studio

A native Python + PySide6 desktop app for experimenting with the existing digital print, scan, motion and grading effects. Open a clip, adjust its treatment, scrub, compare versions, and play a short loop inside the app.

The project version comes from [`_version.py`](_version.py); run `python studio.py --version` to display it. See [versioning](VERSIONING.md) and the [changelog](CHANGELOG.md) for milestone history and compatibility notes.

## Launch on this Mac

After the one-time setup below, launch the native window from the repository directory:

```sh
cd nebula-pipeline
.venv/bin/python studio.py
```

After launch, all experimentation happens in the desktop window. The optional **Nebula Studio.app** wrapper is also included, but Launch Services on the validation Mac denied Python access to the environment under Documents (`Operation not permitted` reading `.venv/pyvenv.cfg`). Its double-click launch therefore remains unverified there; the command above was verified. No system privacy settings were changed. Keep the wrapper inside this repository: it uses `.venv` and is not a self-contained signed installer. Its diagnostic log is `.validation/studio.log`.

For a fresh checkout, install Python 3.11+ and FFmpeg, then create the isolated environment once:

```sh
brew install python ffmpeg
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-desktop.txt
.venv/bin/python studio.py
```

The Python entry point also works on other platforms with PySide6 and FFmpeg on PATH; this milestone was validated on macOS with Python 3.14 and PySide6 6.11.2. Optional startup arguments:

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

The default view is a **composer**: six sections below the preview and seven
macro controls for rhythm, width, instability, texture, brightness, flares,
and magenta. It opens the **Refined 15s** study with every macro at 1×.
**Approved 15s** reloads the earlier study with its original recipe and pixels.

The native editors share a terminal-inspired interface: a system-available
monospaced font, dark panels, phosphor-green controls and a violet playhead.
The synth monitor shows the rendered preview dimensions, RGB format and
play/hold state. The theme lives in [`studio_theme.py`](studio_theme.py) and
affects the interface only; saved compositions and exported pixels are unchanged.

- Select **Whole clip** to adjust the entire piece, or click a section to
  adjust it locally. Sections can be added, duplicated, removed, reordered,
  and given different durations. Their internal events are generated for you.
- In **Geometry**, choose a rectangle, ellipse, circle or regular polygon.
  Width and height scale rectangular/elliptical forms; circles and polygons
  use a diameter measured as a percentage of image height. Polygons have
  3–32 sides. Rotation is available for rectangles, ellipses and polygons.
  The same geometry shapes the luminous source, its echoes and the central
  ray aperture. Signal treatment remains in the **Treatment** tab.
- **Original geometry** retains each source state's authored shape. Sections
  default to **From whole clip** and can override it independently. Geometry
  saves with the composition and supports undo/redo. **New take** keeps the
  shape, diameter, height, sides and rotation; the Width macro still varies
  rectangular/elliptical forms unless locked. Circles remain circular.
- **New clip** starts a 15-second arrangement using the refined Blocks & ghosts phrase.
  Choose other phrases from the section dropdown. Phrases repeat to fill their
  duration; **Rhythm** controls how quickly their internal changes happen.
- **New take** makes a reproducible variation in the current scope. **Keep**
  locks a macro value during variation. **Reset controls** returns that scope
  to 1×, its original geometry and variation; **Undo / Redo** recover composition edits.
- **Save…** keeps the arrangement, macros, locks, variations and a snapshot of
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
