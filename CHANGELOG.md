# Changelog

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
