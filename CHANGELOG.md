# Changelog

## 0.6.7 — 2026-10-05

- Double-click a timeline clip to enter its editing scope. Single-click keeps
  the chosen scope. Repeated occurrences enter the same clip's settings and
  seek to the clicked occurrence. Explain the gesture in timeline help and hints.

## 0.6.6 — 2026-10-05

- Keep the viewport visible when browsing an already-applied effect in Add
  effect. Restore the working preview after leaving a temporary preset audition.
  Inspect preserves existing effect settings; rendering and saved looks are unchanged.

## 0.6.5 — 2026-10-05

- Keep the chosen editing scope when selecting timeline clips. Entire project
  shows only shared effects, without clip settings or navigation links. Label
  Add project effect and Add clip effect to make the destination clear. Clip
  editing is chosen explicitly in Editing; rendering and saved looks are unchanged.

## 0.6.4 — 2026-10-05

- Separate inherited project effects from clip effects and overrides. Entire
  project shows the shared look and links to clips with local settings. Clip
  overrides remain visible when Off, with a Follow project action that keeps
  automation. Rename timeline sections to Clips and Whole clip to Entire project
  across the interface and usage guide. Rendering, document keys and existing
  Studies remain unchanged.

## 0.6.3 — 2026-10-05

- Add a timeline **+ Add section…** shortcut for independent footage. Copy any
  section’s look, automation, framing and duration, or start with the shared look
  and the new footage’s duration. New footage starts at its beginning at normal
  speed, with one play. Additions complete atomically after preparation, support
  Undo/Redo, and cancel safely. Timeline tools wrap in narrow monitors.
  Existing Studies, duplication and source replacement behavior are unchanged.

## 0.6.2 — 2026-10-05

- Explain section footage playback with actual source intervals, effective speed,
  section length and hold/loop behavior, separate from the selected In/Out range.
  Shared sections show Edit shared source and Make independent actions instead
  of disabled trim/framing fields. Rendering and saved timing stay unchanged.

- Reconcile the usage guide and roadmap with shipped section footage, loops,
  Tape damage instances and automation. Add a duration/speed/FPS reference and
  distinguish the earlier Print / Scan editor's limits from the Synth composer.
  Documentation only; application behavior and version remain unchanged.

## 0.6.1 — 2026-10-05

- Clarify timeline resizing with compact **Keep footage speed** and
  **Stretch footage** labels. Tooltips explain source Out limits, retained speed,
  and proportional effects and automation timing. Existing resize behavior,
  saved settings and rendering remain unchanged.

## 0.6.0 — 2026-10-05

- Give timeline sections independent footage from Source, preserving their
  effects and automation. Each section can choose its own video, trim, framing,
  cadence and audio, or return to continuous shared footage. Independent media
  restarts at In on each section repeat and survives duplication, reorder,
  retiming, Undo/Redo, snapshots, Studies and detailed copies.
- Add section Playback speed with optional matching duration. Matching speed
  proportionally retimes section effects and automation; keeping duration
  changes only footage speed. Export assembles each source's audio with preserved
  pitch, including muted intervals, loops, Hold and partial timeline exports.
- Retain existing shared-source rendering and schema 2. Independent footage
  uses schema 3 so older apps reject it explicitly. Studies copy all referenced
  videos locally, preview caches track every active source, and exports protect
  every source asset from being overwritten.

## 0.5.3 — 2026-10-04

- Duplicate selected timeline sections or an automation curve with Command-D
  or the right-click menu. Section selections copy together in timeline order,
  preserving effects, timing, automation, individual loops and complete sequence
  loop groups, with independent identities and the copies selected afterward.
- Copy automation into the next free space after its original in the same section,
  retaining its curve, strength and target. When there is no room, show how to
  make space without changing the section. Duplication is one Undo/Redo step and
  persists through Save/Open; shortcuts stay local to the focused timeline lane.

## 0.5.2 — 2026-10-04

- Add Tape damage's **Pull edges → Keep canvas filled** mode. Horizontal pull
  stretches the interior while anchoring both canvas edges, without exposing
  blank strips, repeating the image, extending flat edge colors or zooming.
  Clean pull / animate and newly added tape passes use this mode.
- Preserve legacy blanking for existing projects and leave other tape faults
  unchanged. Gesture timing and strength remain individually configurable.

## 0.5.1 — 2026-10-04

- Add independent Tape damage instances from the inspector or Add effect browser.
  Each numbered pass has separate settings, bypass, removal and automation.
  New passes start neutral and run after the existing image chain in creation
  order, preserving original module order, seeds and study rendering.
- Keep instance targets through section edits, loops, save/open, detailed copies,
  Studies, snapshots and MP4 exports. Removing one pass clears only its events;
  Undo/Redo restores the pass and its automation together.

## 0.5.0 — 2026-10-04

- Add section-based parameter automation: timed rise, hold and recovery gestures
  with signed strength, smooth or linear easing, and a compact curve editor.
  Animate is available on 18 continuous image-treatment controls.
- Show gestures in a compact timeline lane with edit, move, disable and remove
  actions. Events follow section order, proportional resizing and loops; base
  settings and authored study animation continue underneath them.
- Add a neutral horizontal pull to Tape damage and a Clean pull / animate preset.
  Existing tape fault timing and zero-pull rendering remain unchanged.
- Preserve gestures through Undo/Redo, snapshots, Studies, save/load, detailed
  copies and MP4 exports. Exact event boundaries restore the underlying image;
  preview edits invalidate obsolete prepared frames.
- Preserve generated render versions when converting detailed sequences back
  into compositions. All 121 frozen rendering scenarios retain their pixels.
- Include an editable ten-second portrait example with a one-second pull at 4s.
  Audio reactivity, arbitrary keyframes and Master automation remain deferred.

## 0.4.4 — 2026-10-03

- Keep timeline help, sections and preview settings packed at the top when
  restoring a tall lower pane. Extra height remains below the controls instead
  of stretching tool rows and their gaps. Preserve the saved divider position.

## 0.4.3 — 2026-10-03

- Give the artwork more room with a responsive two-row document/canvas header,
  global Timeline FPS beside Canvas, compact monitor zoom and a persistent top
  Export action. Save As and Save as study move into the Save arrow menu.
- Compact timeline blocks to two lines, distinguish local editing fill from
  selection outlines, and keep existing resize, group stretch, reorder and loops.
  Use thin divider grips with the same comfortable drag area.
- Place prepared ranges directly below the playback scrubber and label the
  prepared frame count for the current playback scope. Keep measured playback
  FPS, partial readiness and error feedback explicit.
- Simplify inspector framing, group Add effect and Edit object with their
  headers, and move contextual Restore into the inspector. Export progress and
  Cancel appear while exporting; completion/error status remains afterward.
- Preserve study rendering, canvas framing, timing, saved documents, snapshots,
  preview cache limits and the user's saved window splits and zoom.

## 0.4.2 — 2026-10-03

- Add Remove beside Bypass in the applied effect list and focused editor.
  Clear settings in the current scope, including section overrides for a
  Whole clip removal. Preserve Undo/Redo, Save/Open and re-adding presets.
- Remember the last successful MP4 export folder across studies and app
  restarts. Cancelled or failed exports retain the previous folder; missing
  folders fall back to the default location.

## 0.4.1 — 2026-10-03

- Stretch or compress multiple selected timeline sections proportionally by
  dragging the last selected section's right edge. Preserve unselected
  durations, loop repetitions and the Effects only / Video + effects modes.
  Add a brighter group handle, selection drag readout and timeline Select All
  shortcut. Frame snapping and duration limits apply to a common scale; release
  commits one undoable edit and Escape cancels the temporary preview.

## 0.4.0 — 2026-10-02

- Add effect and inspector preset replacement now audition on the complete
  current piece before an explicit, undoable Apply. Before/Preview, sampled
  playback and scrub stay temporary; Cancel and Escape create no edits.
- Add scoped/current-frame effect explanations and a navigable How this look is
  built overview with temporary contribution bypass comparisons.
- Reuse A3 preview routing and its shared 192 MiB frame budget, with temporary
  360 px quality and original-clock sampling at up to 12 fps. Subject cutout
  preparation remains explicit; slow studies can take seconds per new frame.
- Use a compact native list and floating macOS audition window with pinned
  transport/actions. See `docs/visual-effect-discovery-delivery.md` for native
  findings, preservation checks, measurements and limits. Existing study
  rendering and saved-document formats remain compatible.

## 0.3.0 — 2026-10-02

- Add named composition snapshots, same-frame A/B preview, undoable restoration
  and removal, and video dependency packaging for saved studies. Reuse A/B
  packets within one bounded cache with stale-worker rejection. Add
  Subtle/Moderate/Strong effect-scoped auditions with selected creative controls,
  protected timing defaults, recorded exploration seeds and explicit
  Keep/Discard. A/B is preview-only; export uses working B. Existing studies
  remain visually unchanged.

- Add Creative controls for Tape damage, Frame jitter, Ghosts and Particles.
  Preserve animated recipe values through bounded relative adjustments and
  additive copy-count offsets. Keep fixed base edits in Parameters with visible
  adjustment annotations; support inherited/neutral section values, reset,
  bypass, history and portable save/open. Add neutral-default trail brightness
  and collect inspector base states during compilation without changing study
  pixels. Particle models open Creative motion directly from Object.

- Add New piece… in the toolbar and File menu with Text, Shape, Model, Video
  and Remix a study choices. Generated pieces start with visible material,
  one six-second section, the current canvas/FPS and Object controls ready.
  Reuse existing effects, import, save/open and unsaved replacement flows;
  preserve original studies and rendering defaults.

- Give the monitor a vertically resizable workspace with a saved divider position.
  Keep zoom, playback and FPS visible above expanded, scrollable timeline/export
  controls; improve default viewport space and keep small windows usable.

- Add automatic preview warming, explicit scoped preparation, cached-range display
  and selected-section playback with original absolute clocks. Bound pending
  deliveries together with cached frames, prioritize seeks and pause warming for
  export. Retain proven-unaffected frames across local visual edits while clearing
  conservatively for global changes. Keep slow uncached playback updating.

- Add a visual Study browser with lazy still thumbnails, a larger selected preview,
  search, source categories and persistent favorites. Keep the compact picker,
  dates and reversible removal. Library preferences and caches stay separate
  from recipes and footage; loading uses the document replacement guard.
- Add document identity, visible unsaved status, Save/Save As and atomic JSON
  writes. Protect source media and bundled recipes, and guard document replacement
  through Open, Studies, presets and completed imports. Add window-scoped editing
  and transport shortcuts while preserving text and parameter keyboard behavior.

- Use compact play/pause icons in the playback controls, with state-aware
  tooltips and accessible labels in both native editors.

- Keep the Studies picker compact and add timeline context-menu looping, preset
  and custom repeat counts, removal, Shift-click ranges and Command-click toggles.
  Multi-selection repeats the selected sequence in order, with visible shared
  section views and correct seeking. Preserve groups through save/open, editing,
  reordering and undo; keep legacy arrangements and continuous source clocks.

- Show a date beside every Study name and add a date-sortable Study manager
  with multiple selection, reversible removal and restoration. Record timestamps
  for new saves; use original file dates for legacy local Studies and fixed
  introduction dates for built-ins. Keep media paths and compositions intact.
  Explain total plays and continuous footage in the timeline Loops tooltip.

- Add Portrait / unstable CRT and its Source treatment: faster irregular bars,
  distinct square flashes sampled before the main slices, and existing Tape
  damage applied to the footage. Add opt-in timing scatter, nonlinear travel,
  independent flash scatter and flash-source selection. Previous recipes keep
  their exact regular timing and rendering.

- Add Portrait / CRT bars and the Cyan / CRT bars Source treatment: restore the
  earlier full-width bar animation while keeping the stronger vertical CRT
  texture and tonal treatment. Add faint square flashes with independent opacity,
  interval, duration and shape controls in Slice echo. Flash opacity defaults to
  zero; existing recipes and saved Studies are unchanged.

- Add the independent Portrait / fractured CRT recipe and Cyan / fractured CRT
  video treatment, with stronger vertical phosphor lines, solarized tonal relief
  and irregular negative image patches. Add opt-in fragment width, stepped
  edges, negative exposure, pre-print softness and solarized highlight recovery.
  Previous portrait recipes, framing, timing and defaults remain unchanged.

- Refine the cyan portrait as an independent Cyan exposures Study and a Cyan /
  filmed exposures video treatment. Add optional diagonal slice seams, pale
  highlight preservation, brightness-shaped opacity, event fades and phosphor
  wear. Add global video-source rotation with uniform scaling and aligned
  foreground masks. New controls default to zero; the first portrait recipe
  and previous Studies retain their rendering.

- Add reusable Chroma print, Slice echo and Screen mesh treatments for footage,
  objects and text, plus the Cyan / slice screen video treatment preset. Add a
  local Portrait / cyan signal recipe with ten seconds of continuous source
  motion, pale cyan exposure, displaced pink image fragments and tilted RGB
  phosphors. Controls include contrast, palette, slice motion, tint and screen
  texture. Filter subpixel patterns consistently in previews, freeze all values
  in the local Study, and leave previous Studies and media untouched.

- Add Text / opium, a 4.5-second editable monochrome Study with three exposure
  pulses, a bold word and an opening serif echo. Stretch echo and Signal etch
  are reusable treatments for generated sources and imported footage, with
  independent timing, grain, light scatter and shape controls. Add bundled
  Bodoni Moda and an optional alternate echo typeface for text. Freeze the
  recipe separately; existing Studies keep their approved rendering.

- Replace More/Fewer controls with expanded groups and a per-tab control filter.
  Add effect sliders, compact two-decimal values and percentage display for tiny
  quantities without rounding saved settings. Put text wording first in Object.
- Show measured preview FPS separately from export FPS, follow wall-clock
  playback and prepare cancellable full-loop previews in a bounded memory cache.
  Debounce edits, reuse compiled inspector state and cache held subject masks,
  including continuity, without changing export or study rendering.
- Add a visible MP4 export progress bar with percentage and frame count, plus
  clear completion, cancellation and error states.
- Add per-section timeline loops. A section can repeat up to 32 times in place;
  total duration, preview and export follow the repeated arrangement, while
  older compositions default to one loop. Each repetition restarts the edited
  section's cues, including custom durations and rhythm changes.

- Replace Lost transmission's wrapped words with large centered single-line
  lettering. Use the existing size, width stretch, line-width limit and adaptive
  repetition controls; retain the full phrase and previous saved layouts.

- Keep all words large in Lost transmission with centered long-word wrapping
  and fewer repetitions when needed. Add editable Wrap after characters and
  Repeat size floor controls to Text; line spacing, size and width remain
  adjustable. Preserve original reveal timing, canvas proportions and saved
  layouts; both new controls default to off in existing documents.

- Refine the Phosphor drift, Lost transmission and Night monitor text Studies
  with exposure washes, broken-sync interruptions, repeated word groups and
  worn CRT glass with colored halation. Preserve their first versions in the
  Studies menu and retain the approved Pressure recipe and existing documents.
  Text repetition and width limits remain editable; Broadcast wear's new
  Signal and Screen tabs expose source-independent effects for generated art
  and footage. Outages are deterministic and independent of render resolution.

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
