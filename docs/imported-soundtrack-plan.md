# Imported soundtrack foundation

Recorded: 2026-10-10. Scope: roadmap B1. Status: delivered in 0.10.0.

Follow-up: continuous frequency-band responses shipped in 0.11.0; see the
[radial/audio Study plan](radial-audio-study-plan.md). The scope below records B1.

## User outcome

Import one soundtrack into an existing piece, see its waveform, trim it and
place it on the project timeline. Hear it while previewing and export it in
sync. Clips still determine project duration. Audio analysis and effect mappings
are the next milestone, not part of this release.

## Document and timing contract

- Optional `soundtrack` data with a stable `id`, name, absolute/resolved local
  path, probed duration/sample rate/channels, `in`, `out`, nonnegative project
  `offset`, `end_mode` (`silence` or `loop`), `gain` (0–1) and `export_audio`
  (`soundtrack`, `footage`, `silent`). New imported tracks default to soundtrack
  export. Removing the track returns to the existing footage-audio behavior.
- Source time is In + project time - offset within the trimmed interval. Loop
  wraps that interval; silence ends playback there. Clip repeats/reorder/resize
  never retime this project clock. Previewing selected clips seeks to their
  original absolute times, including discontinuous selections.
- Soundtrack documents use schema 4 so older apps reject unsupported audio
  explicitly. Documents without soundtrack retain existing schemas and pixels.
- Save/Open, snapshots, detailed copies, Undo/Redo and portable Studies retain
  authored audio settings and media. Relink retains track identity and validates
  the trim against replacement media. Missing media has an actionable state.
- Monitor mute and volume are session preferences, separate from saved track
  gain/export selection. Changing them never edits the composition.

## Interface

- A compact Soundtrack action beside the timeline opens a nonmodal editor.
  A waveform lane appears only when a soundtrack exists and supports seeking.
- Editor: import/replace/relink/remove; In/Out/Start controls; end behavior;
  output volume (0–100%) and explicit export audio choice. Clear source and used duration.
- Import/probe/waveform work happens off the UI thread, is cancellable and
  rejects stale results after replacement/close. Derived waveform is bounded
  and regenerable, not embedded in the composition.
- Playback starts/stops/seeks with the existing transport; soundtrack timing
  follows real time even when video preview drops frames. Report unavailable
  audio devices/media instead of silently claiming synchronized playback.

## Work packages

1. Soundtrack data/probe/waveform and export assembly — GPT-6.1 Sol. Independent
   module and tests plus composition/sequence/export normalization integration.
2. Soundtrack preview transport — GPT-6.1 Sol. Isolated Qt Multimedia adapter,
   fake-backend seek/loop/pause tests, no main-window edits.
3. Compact waveform/editor widgets — GPT-6.1 Sol. Isolated widgets and focused
   tests using the existing Studio theme, no main-window edits.
4. Main-window integration, media portability/protection, review — root. One
   owner for shared UI, history, cache lifecycle and study asset packaging.
5. Release validation, documentation, merge and installation — root.

## Validation

- Generated tone fixtures verify trim, positive offset, looping, silence,
  volume, partial exports and explicit soundtrack/footage/silent selection.
- Malformed/NaN/infinite settings reject cleanly; missing media and cancellation
  preserve existing files. Export cannot overwrite any authored media.
- Transport fake/backend tests cover play/pause, scrub, project loop, selected
  clip jumps, offset silence, trimmed looping, mute, stale loads and cleanup.
- Save/Open, independent snapshots, Studies media copying, detailed copies and
  undo/redo preserve identity and playback settings. No file I/O in paint/tick.
- Run relevant existing export, source, preview/history and frozen-study tests.
  Inspect native UI at normal/narrow sizes, build and verify the macOS app,
  verify an actual audio/video export and record concrete limits.

## Deferred

Frequency analysis/mapping (B2), multiple tracks, live input, mixing soundtrack
and footage, audio fades/effects, beat detection, word morphing and a DAW editor.

## Delivery verification

- 78 soundtrack core, transport, widget and Studio integration tests passed,
  including the opt-in native muted-audio test. Export checks decode generated
  tones to verify trim, offset, silence, loops, volume and partial ranges.
- Existing frozen Study, Study library, exploration, footage/audio retiming,
  composition, sequence, preview scope and cache checks passed. A timing test
  now tolerates elapsed clock time instead of expecting exactly zero time to
  have passed when Play is clicked.
- A rendered three-second MP4 was verified to contain H.264 video and 48 kHz
  AAC audio, both exactly three seconds long. Local QA artifacts are under
  `output/soundtrack-qa/` and are not packaged as Studies.
- Reviewed the compact editor and waveform layout, built and signature-checked
  the macOS app, and verified opening, relinking and playback in the installed
  application. A cold-load issue found through the native file picker was
  resolved by deferring media loading until the next Qt event-loop turn;
  cancellation prevents a closed or replaced backend from starting stale work.
- Native seeking remains approximate and preview trim loops may have a small
  gap. Export assembles timing separately using audio samples. Frequency
  analysis and parameter mappings remain B2.
