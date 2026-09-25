# Changelog

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
