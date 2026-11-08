# Documentation review, 2026-11-08

[Documentation](README.md) · [History inventory](history.md)

## Baseline and scope

The working checkout was clean on `codex/pleated-live-midi`, commit `979d940`,
with `_version.py` and bundle metadata at 0.84.0. Review started from that source,
not `main`. Documentation changes are isolated on `codex/documentation-audit-084`.

The inventory covers root documents, all maintained Markdown under `docs/`, asset
READMEs and the Ableton integration. Requirements and packaging/installation
scripts were read as evidence. Dependencies, generated files, third-party license
texts, personal projects and external UX reports were not rewritten. No installed
Nebula/Ableton session was opened, stopped, rebuilt or updated.

## Editorial result

The original README had 2,115 lines and 21,000 words. Its opening served newcomers,
but the rest mixed a user manual, detailed parameters, recipe revisions, test
reports and local installation history. That length was inappropriate for an
entry point; the parameter detail remains useful as reference.

The README is now 78 lines / 569 words. It introduces representative work, the available local launch path,
limitations and navigation. The first-piece guide leads through visible material,
effects, save and export. Detailed controls moved to editing, video, sources/studies
and effects references. Sound now has a current guide independent of its versioned
DSP narrative. Montage, inspector and monitor pages lead with tasks rather than
release identifiers. The history index classifies retained records; the old
creative/audio roadmap is archived with a current status map in its place.

Corrections include:

- `studio.py --synth` is the composer entry point; bare `studio.py` opens the
  earlier Print / Scan editor. Local builds are not a public notarized installer.
- Sound audition, applied project settings, file saves and movie output are
  distinct. Closing no longer silently discards a draft; the user resolves it.
- MIDI is session-only monitoring, with separate Pleated/Color-wave channels;
  DAW audio is not captured in MP4. Montage exports its own soundtrack or silence.
- Effect auditions respect selected monitor resolution, including Full canvas.
  The old fixed-360-pixel description was superseded in 0.48.1.
- Current controls use Main text / Apply main text, Output canvas / Fit content,
  View zoom / Fit view and Preview resolution / Prepare range.
- Active macOS system fonts and static GLB/glTF import are supported. The former
  font/model asset READMEs made broader claims that obscured these features.
- User effect ordering is implemented. Tension sound, arbitrary signal routing,
  multitrack audio and final-image sonification are not marked complete.
- Built-in studies, tracked examples and personal media-dependent variants are
  distinguished. The performance runner's local fixture requirements are explicit.

Historical changelog entries are preserved verbatim; only the introduction and
Unreleased documentation notes were added. Past screenshots remain within their
historical delivery record. No new screenshot is presented as current UI evidence.

## Evidence and checks

Source inspection included desktop entry points/packaging, study registrations,
source and effect metadata, text/reading layout, model import bounds, sound-session
resolution, instrument/sequencer/MIDI paths, Montage navigation and export routes.
Built-in study factories were inspected without rendering full studies. The
relative-link check covers 317 file/image destinations and heading anchors across
53 maintained Markdown documents. Every document is reachable from the README;
all four linked PNGs decode successfully.

Commands were compared with their parsers and requirements. `studio.py --version`
returned 0.84.0 and `scripts/sync_version.py --check` passed. Installation, builds,
asset generation and the native performance runner were not executed merely to
validate their instructions. Existing dependencies were reused without installing
anything: Python 3.14.6, PySide6 6.11.2, NumPy 2.5.3, Pillow 12.3.0, pytest 9.1.1.
Tests imported code from this checkout.

The completed focused tests comprise **98 passes and one failure**, with Qt set
to `offscreen`. No real MIDI port or DAW was used.

| Coverage | Result |
| --- | --- |
| `test_synth_sound_session.py` | 14 passed: drafts, applied sound, save, export and session-only MIDI UI. |
| `test_synth_sound_pattern_ui.py` | 5 passed; 1280×800 layout case failed (see below). |
| `test_synth_output_ui.py` | 14 passed, including all three layout sizes in fresh processes and decoded export-frame equality across preview settings. |
| `test_synth_montage_selection.py` | 11 passed: target/material separation, drafts, insertion and replacement. |
| `test_synth_montage_blocks.py` | 10 passed: short cuts, list identity, selection and reversible view framing. |
| `test_synth_object_groups.py` | 12 passed, including three layouts in fresh processes. |
| `test_synth_live_midi.py`, `test_synth_pleated_midi.py`, `test_ableton_midi_recovery.py` | 19 passed with fake ports/devices. |
| `test_synth_new_piece_ui.py` | 10 passed: create/remix/import, edit, save and reopen. |
| Effect-discovery monitor-resolution cases | 3 passed at 360 px, 720 px and Full canvas. |

These are bounded behavior checks, not a fresh full rendering baseline or a
complete application/platform certification. `git diff --check` passed; changes
are confined to Markdown, with source, tests, presets, metadata and licenses
unchanged.

## Separate possible UI issue and verification limits

`test_synth_sound_pattern_ui.py::test_all_steps_and_precise_editor_fit_without_horizontal_scroll[1280-800]`
fails in a fresh offscreen process: the selected-step numeric editor's bottom
point is at y=464 in a viewport with valid y=0–463. The 1440×900 case passes.
This is evidence of a one-pixel layout/test discrepancy in the existing source;
it does not establish the appearance in the installed native app. No application
or test code was changed to make it pass.

An initial combined UI run accumulated substantial stylesheet work. It was
interrupted after about 12 minutes in `apply_theme`; Qt then exited with a
segmentation fault. That incomplete run is not included in the counts above.
The bounded suites and individual layout checks were rerun in fresh processes.
This does not demonstrate a crash in an ordinary Nebula session.

Still unverified here: native installed-app appearance, actual audio/DAW latency
and instrument behavior, clean-machine installation, non-macOS operation and
historic performance/hardware measurements. External provenance links were
retained; this review checked relative navigation, not fresh availability or
third-party documentation accuracy. The interpretation that the README should
be shorter is an editorial judgment; source labels, routing and test outcomes
above are directly checked facts.
