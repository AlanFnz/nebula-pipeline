# Changelog

## Unreleased

- Freeze the nine existing starter recipes and named/default presets. Add
  rendering versions independent of document schemas, retaining the original
  phosphor renderer for older projects. A 3,385-frame, 99-case manifest protects
  the current visual results across canvas formats and rendering resolutions.
- Edge phosphor's Region tab adds a reusable directional fade with object or
  canvas anchoring, position, width, angle, curve and light blending. The original
  Neck dissolve remains available as Profile preset. Generic treatments receive
  explicit render inputs instead of looking up a head source in the preset.
- Add Profile / clear silhouette, an independent eight-second variation with
  more readable facial contours and calmer scan streaks during holds. Object →
  Facial definition gently emphasizes facial geometry; zero retains the original
  mesh projection. Both prior profile starters remain unchanged.
- Opening a document clears the starter picker to Choose a starter, so an
  unrelated selection no longer appears to identify the current composition.

- Edge phosphor adds Neck dissolve for the solid head model. It fades the
  neck's bright detached edges and blends the lower cutout into the textured
  backlight, following object placement, scale and roll. Both profile starters
  enable it; zero restores the previous outline and saved settings stay intact.

- Fix the rectangular lighting/scan boundary when resizing profile starters
  to Stories, square or other larger canvases. Edge phosphor continues its
  textured backlight beyond the head's finite height; Scan drag carries the
  signal to the new canvas edges. The head keeps its size, proportions and
  placement. Canvas coverage defaults to Extend to canvas, including in saved
  profiles; Artwork bounds retains the earlier framing. Both original native
  profile clips keep their exact pixels.

- Profile / signal echoes adds an eight-second variation as an independent
  starter: green lock, overload, falling red scan, violet echoes, exposure flare
  and signal rupture, then a green return. Six editable sections reuse Ghosts /
  trails, Exposure flare and Signal drift alongside the fixed head and textured
  signal background. The original four-second starter stays unchanged.

- Signal background fills deep blacks with Refined signal's green-black tone,
  fine grain and horizontal noise. The profile starter enables it across all
  four sections, including the silhouette and recording margins. Background
  level, grain, tint, scanlines, shadow reach, FPS and mix are editable; bright
  contours remain unchanged. Disable it to restore the original profile.
  Other starters and saved compositions keep their previous rendering.

- Profile / phosphor scan adds a fixed head silhouette study: 61 frames at
  15 fps, four editable sections, green/red backlight and clustered scan tears.
  Model silhouette reuses the bundled head mesh with pose/framing controls.
  Edge phosphor and Scan drag are independent reusable treatments with held
  grain, contour echoes, chromatic streaks, overload and tracking controls.
  Object X/Y, scope overrides, neutral bypass, save/open, Undo/Redo, detailed
  copies, low-resolution finishing and full-size export are supported. All new
  modules start disabled in existing studies.

- Object adds shared Position X/Y sliders and numeric inputs in canvas pixels,
  with scope-aware offsets and Reset position. Placement moves the full source
  group and attached ghosts/halos before treatments, preserving motion, canvas
  backgrounds, existing artwork and neutral rendering. Supports all source
  families, canvas resizing, Undo/Redo, saved/detailed documents and export.

- Object replaces the Geometry tab with one source selector and contextual
  controls for geometric signals, ink stamps/custom artwork and particle models.
  Source replacement retains treatments, authored parameters and section timing;
  returning to an authored family restores its source choreography. Includes
  scope-aware edits, starter restoration, Undo/Redo and shared Timing shortcuts.

- A persistent Total display beside playback follows the sum of all sections,
  including automatically retimed gestures.

- The Effects inspector separates Applied effects from a collapsible Available
  effects catalog. Visible rows show On, Intermittent, Off or Bypassed state and
  highlight the inspected effect. Lists follow effective section/whole-clip
  usage, including inherited recipes, local overrides and Undo/Redo. Browsing
  effects leaves the composition unchanged; the existing preset controls add
  them explicitly. All rows use the main inspector scroll area.

- Canvas format changes preserve artwork size, proportions and center instead
  of stretching it. Optional Fit subject scales uniformly; procedural noise and
  backgrounds fill the new canvas. Saved artwork references survive repeated
  format changes, Undo/Redo, detailed copies and exports.

- View-only zoom with Fit, percentages, 100%, drag panning and pointer-centered
  Ctrl/⌘ + wheel zoom. A wider draggable divider resizes the inspector. The main
  app opens fullscreen initially and remembers window mode, geometry, panel
  width and zoom across launches.

- Slowing Gesture speed no longer lowers Motion FPS. Ink motion now samples its
  hold clock before scaling travel, keeping smaller pose changes at the selected
  cadence instead of increasingly long freezes. Shared clock scaling follows
  the same rule; original-speed recipes retain their approved frames.

- Master tab adds composition-wide brightness, contrast and saturation after
  effects, background and transitions. Includes bypass, individual/full reset,
  Undo/Redo, save/load and independent detailed-copy controls. Neutral and
  bypassed Master preserve original pixels, including low-resolution finishing.

- Dropdowns, numeric fields and sliders pass wheel/trackpad input through to
  their scroll panel, including focused controls. Click selection, typing,
  keyboard arrows and dragging remain available throughout the native editors.

- Ink timing is now one shared setup for every section. Existing local timing
  overrides consolidate into a complete global profile, preventing different
  loop lengths or scene clocks from causing jumps at section boundaries. Timing
  has an explicit global scope in the inspector. Whole-cycle ink sections resize
  together as durations/speed change; arbitrary arrangements keep their lengths.
  Appearance controls retain section scope, and untouched recipes keep their
  earlier frames. Undo/Redo, save/load and detailed exports preserve the profile.

- Ink bloom has Look / Timing tabs and independent Unfold, Stay unfolded, Fold
  and Stay folded durations in seconds. Gesture speed scales its motion without
  changing frame jitter or background clocks. Turn motion follows the retimed
  stages; the inspector resolves recipe durations and section ranges, shows the
  resulting loop length, and supports reset, Undo/Redo and
  saved/detailed editing. Earlier percentage-based gestures remain pixel-exact.

- Reusable Low-res finish preserves the 360 px preview texture in full-size
  exports. Working resolution and Soft / Crisp pixels enlargement apply to the
  complete render, including backgrounds and timeline transitions. Includes
  four looks, whole-clip/section scope, Undo/Redo and saved/detailed controls;
  existing studies keep native rendering until the effect is enabled.

- Reusable Frame jitter effect adds held horizontal/vertical shifts, rotation
  and scale variation, with independent FPS, strength and movement seed. Its
  subpixel transform runs before finishing, preserves highlights and does not
  move the fresh print background. A Mixed media / two bursts starter exposes
  the wider reverse second gesture as two editable studio sections.

- Replaceable Ink bloom silhouettes: square, circle, triangle, polygon and
  imported artwork share the existing unfold/turn/refold animation. Custom
  transparency or luminance masks retain holes and proportions, use the selected
  inks and are embedded in saved documents. Native import, width/height/rotation,
  polygon sides, Undo/Redo and detailed-editor support preserve the original
  burst and the independent print background.

- Ink bloom now uses fresh background noise on each held frame, replacing the
  visibly translated/wrapped paper field. Independent noise amount, size,
  clumping and tone controls protect the approved ink figures and motion.
  Original paper preserves existing saved clips and remains selectable.

- Ink bloom starter: a 3.53-second, 15 fps procedural mixed-media gesture with
  seven irregular CMY/white stamps unfolding, turning and refolding in one
  editable section. Reusable Ink bloom controls cover shape, palette, depth,
  motion, manual opening and cycle timing.
- Reusable Print surface treatment adds persistent charcoal-paper fibers,
  ink grain/erosion, frayed edges, held registration, texture boil and dust to
  any generated source. Both new effects are disabled in existing studies.

- Non-destructive canvas formats: original 5:4, Stories/Reels 9:16, portrait 4:5
  and 3:4, square 1:1, landscape 1.91:1 and widescreen 16:9. Adaptive subject
  framing keeps particles proportional on narrow canvases while noise and tape
  treatments render edge to edge. Canvas settings persist, support composer
  Undo/Redo, and travel into detailed copies and exports.
- Starters dropdown with all five built-in studies, explicit Load starter and
  independent editable copies that retain the selected canvas format.
- Preview quality is now independent of MP4 resolution; export always uses the
  full canvas dimensions shown in the toolbar.

- Carry orbit return rotation keeps the head and cloud in one rotating frame,
  retaining accumulated rotation as particles gather instead of unwinding toward
  the earlier head angle. Enabled in the current Expand / orbit study; older
  documents retain their original return and pixels.

- Faster assembled-head turning with an independent, gated turn clock; centered
  head/cloud rotation removes the expanded volume’s offset orbit. A model-space
  neck feather softens the mesh cutoff. The current Expand / orbit study uses
  these controls while preserving its two bursts and tape treatment; saved
  earlier studies retain their output.

- Portrait head with smoothed geometry and eye surfaces, plus opt-in particle
  depth occlusion to suppress internal/far-side points. The earlier head asset
  and all saved particle studies retain their pixels.
- Reusable Tape damage effect: source-only tracking slips, jitter, short scanline
  dropouts, chroma lag/bleed and head-switch errors. The current Expand / orbit
  study replaces its drawn bars and flare with tape faults while preserving
  both expansion/return bursts and their easing.
- Expand / orbit particle release: outward dispersion into a broad 3D volume,
  delayed vertical-axis rotation, adjustable speed/direction and expansion threshold.
- Impulse motion separates expansion/gather durations from cycle length, with
  an editable velocity peak. The revised Expand / orbit study has exactly two
  expansions in 15 seconds, restrained violet/white color, and
  tracking breaks timed around the bursts. Saved orbit documents and both earlier
  particle studies retain their previous pixels.
- Anatomical Human head target sampled from a bundled CC0 MakeHuman mesh, plus
  opt-in Surges motion with acceleration, staggered curved arrivals and rebound.
- Reusable Signal interference effect and a three-section Particle signal study
  combining it with warp, flares, grain, color separation and tracking breaks.
  Original particles retains the first study; saved Gentle motion is unchanged.
- Native save/export dialogs suggest the composition's name in Documents/Movies.
- Opt-in Particle attractor effect with persistent dots assembling around hidden
  procedural head, sphere and ring surfaces. Controls cover assembly cycles,
  dispersion, turbulence, point density/size, rotation, color and signal texture.
- Separate one-section **Particle head 15s** example, native effect controls,
  composition save/open, undo/redo and shared preview/export rendering.
- Existing presets leave particles and interference disabled. Approved, Refined
  and original particle studies keep their prior rendered pixels. The new human
  mesh is bundled with provenance; no reference media pixels are used.

## 0.2.0 — 2026-09-25

### Added

- Native composition view with six reusable sections and seven macro controls,
  whole-clip or local adjustments, phrase repetition, reordering, duration
  changes, deterministic takes with locks, and composition undo/redo.
- Self-contained composition documents and an independent detailed-copy editor.
  Neutral composition controls preserve all frames of the approved study;
  the renderer and its bundled recipe are unchanged by the composition layer.
- Source-free Nebula Synth desktop mode (`studio.py --synth`) with deterministic
  luminous slabs, irregular Venetian-blind rays, warp, separation, smear,
  bloom and raster modules.
- Versioned synth JSON presets with module ordering/toggles, typed controls,
  locked-parameter variation, treatment FPS holds, separate export FPS and
  atomic FFmpeg loop export.
- Editable 15-second reference-study cue sequence with deterministic cuts,
  numeric morphs, horizontal sweeps, flash events, sequence JSON round trips
  and one continuous export path.
- Bundled 323-cue composite study with asymmetric exposure flares, rapid
  filled/fragmented/outline changes, split magenta fill, local signal clouds,
  grainy ghosts, per-frame registration and signal softness.
- Sequence state editing, cue-linked duplication, locked variation and
  selection-driven scrubbing, with validation that preserves the last valid
  sequence after an invalid edit.
- Renderer and export regression checks covering time determinism, schema
  round trips, treatment holds and generated MP4 output.

### Compatibility and known limits

- The synth generator is source-free in this milestone; input-video modulation
  is planned for a later phase. The existing clip pipeline remains unchanged.
- CPU rendering is deterministic but is not promised to sustain full-resolution
  real-time playback on every machine.

## 0.1.0 — 2026-09-09

First native desktop milestone, following the existing `v0.0.1` pipeline release.

### Added

- PySide6 studio with an embedded preview, existing effect controls, stage bypass and output inspection, timeline scrubbing, and one-to-three-second loops.
- Same-source/frame A/B settings snapshots with a draggable comparison divider; compatible JSON preset loading and saving.
- Current-frame-first asynchronous proxy rendering, edit coalescing, stale-result rejection, cancellation, bounded caches, and full-resolution still inspection.
- Full-resolution loop or whole-clip MP4 export with fixed settings per job, cancellation, source protection, and atomic destination replacement.
- Engine, FFmpeg and Qt functional checks, a repeatable preview measurement script, launch/use documentation, and a canonical project version with checked macOS metadata.

### Changed

- Preview, legacy frame processing and export share a consistent print → scan → wobble → grade order.
- Seeded randomness is independent per effect and absolute output-frame index. Temporal variation uses deterministic interpolated knots instead of the global random walk; scrubbing and effect bypass no longer re-roll other effects.
- The legacy TUI preview shows the actual selected frame instead of a low/mid/high parameter sheet. Existing entry points and preset values remain available.

### Compatibility and known limits

- Seeded images intentionally differ from earlier versions. Existing preset values load, but historical renders require their original version. Missing/null seeds now resolve to 42.
- Full-resolution pixels match before encoding; MP4 uses lossy H.264 with 4:2:0 chroma and contains no audio. Odd dimensions are padded by up to one pixel.
- Proxies approximate fine noise, dust and subpixel movement. CPU rendering is not guaranteed to run at real-time full resolution. Accurate seeking decodes from the beginning, making late positions in long clips slower.
- Direct Python launch is verified on macOS. The optional `.app` wrapper encountered Documents-folder access denial on the validation host. It is a local environment launcher, not a signed or self-contained installer; no system privacy settings were changed.
- One clip at a time, fixed stage order, no audio playback, and no multi-clip editing or undo history in this milestone.

### Validation

The milestone suite covers shared-render parity, deterministic scrubbing and effect isolation, decode-grid parity, range-export frame identity, cancellation cleanup, rapid UI changes, same-time A/B after bypass, late-result rejection, playback, presets and GUI export. Version consistency is checked separately by `scripts/sync_version.py --check`.

Reference observation on the validation Mac: a 720 × 1280 clip at a 270 × 480 proxy showed the first frame in 275 ms and prepared a two-second / 24-frame loop in 734 ms. A cached blur edit showed the current frame in 124 ms. These are local observations, not throughput guarantees; see the README for details.

## 0.0.1 — 2026-04-27

Existing initial release: Python analog degradation pipeline with video generation, frame extraction, per-frame wobble/grain, and FFmpeg reassembly. Recorded from the repository's original `v0.0.1` tag; that tag is unchanged.
