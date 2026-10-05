# Timed effect automation delivery

Implemented 2026-10-04 on `codex/timed-effect-automation`, based on 0.4.4.
Merged through PR #21, released and installed as 0.5.0 on 2026-10-04.
The validation below records the original implementation and isolated review.
Current workflow: [README](../README.md).

## Artist workflow

In Effects → Parameters, supported controls have an **Animate…** action. Once
an event exists, this becomes **Automations (count)…** and the parameter label
identifies its **Base**. The modal editor authors a draft: target section,
Start/Rise/Hold/Recover in seconds, signed Change amount, Smooth/Linear easing,
and Enabled. It shows a curve, duration/end and a section-specific inactive
warning. **Quick pull** proposes a 15% rise and 85% recovery, with no hold.
Apply validates the whole document and creates one history step. Cancel,
Escape and closing the dialog discard the draft. Invalid bounds or enabled
same-target overlaps remain in the editor with the conflicting IDs/path.

**Automations…** is always available beside Arrange sections and supplies the
keyboard-accessible list with Add, Edit, Enable/Disable and Remove. Events are
section-owned even when opened from the Whole clip inspector; default section
selection follows the playhead. Enabled events on different targets may overlap.
Disabled events remain visible and reenabling validates conflicts.

A 30px automation lane appears below the existing 62px section surface only
when events exist. Its envelopes/tooltips show absolute times and owning section.
Click selects, double-click edits, body drag moves within the base section, and
right-click exposes Edit/Enable/Disable/Remove. When several targets overlap,
separate target submenus give unambiguous access. Repetitions select/edit the same
authored gesture. Drag is a private preview until release; Escape cancels and
one release creates one undo entry. Section drag, resize and loop hit targets
remain on their existing surface. The scroll container grows by the same 30px.

Bypass and preset replacement retain automation. Remove effect removes targeted
events in the selected section, or all sections for Whole clip removal, together
with settings; Undo restores both. Restore parameter changes the base only.
Diagnostics resolve effective values at the same evaluation point as rendering,
and explain when an active gesture targets a disabled/bypassed module.

## Shipped targets

| Effect | Canonical parameter paths |
| --- | --- |
| Tape damage | `tape.pull`, `tape.tracking`, `tape.jitter` |
| Signal drift | `warp.amount` |
| Signal breakup | `breakup.amount` |
| Color separation | `separation.amount` |
| Ghosts / trails | `smear.amount`, `smear.opacity` |
| Bloom | `bloom.strength` |
| CRT capture | `crt_capture.bend` |
| Raster / grain | `raster.grain`, `raster.lines`, `raster.chroma`, `raster.line_noise` |
| Chroma print | `chroma_print.exposure`, `chroma_print.mid_saturation`, `chroma_print.warm_color`, `chroma_print.mix` |

Discrete choices/counts/seeds, rates/cadence, cache dimensions, ink timing
sentinels, text/artwork/source changes and Master are excluded. Arbitrary
keyframe graphs, standalone envelope looping and audio modulation are deferred.

## Data, clocks and preservation

Sections optionally store `automations`, with section-local unique IDs, canonical
path, signed amount, enabled/easing and explicit `start_fraction`,
`attack_fraction`, `hold_fraction`, `recovery_fraction`. Durations are positive;
individual stages may be zero. JSON normalization rejects booleans as numbers,
nonfinite values, unknown targets, duplicate IDs, bad bounds/easing and overlapping
enabled intervals. Amount is bounded to the target's full parameter span.

The compiler expands output-timeline seconds per section placement and internal
loop. Fraction timing scales exactly once with resize, independent of procedural
`effects_rate`; FPS changes sample the continuous curve on the new grid. Stable,
bounded hashed compiled IDs prevent identity strings growing across repeated
imports. Both authored document totals and compiled sequences are bounded at
131,072 events. The larger section cap deliberately retains legitimately
expanded detailed copies, rather than failing after 128 imported events; compile
rejects excessive loop expansion before allocating it.

`resolve_sequence_frame` applies automation after cue interpolation and
inherited/fixed/Creative settings, before rendering: clamp(base + amount ×
envelope). Off/bypassed modules stay off. Zero contributions return the original
resolved preset without normalization or resampling. Half-open endpoints use an
8-ULP tolerance solely to remove floating-point residue from equivalent fraction
and frame-grid timestamps; zero-duration onset steps remain explicit.

`composition_from_sequence` converts detailed sequence events into the single
imported section and removes them from its embedded source. This avoids double
application, preserves render_version, and makes subsequent loop/resize/reorder
behavior explicit. A manually constructed composition containing automation
only inside its embedded source is rejected by compile with an instruction to
import through `composition_from_sequence`; events are never silently discarded.
The existing composition import limits (300s base section) remain in force.

Save/load, snapshots, Studies and detailed copies retain the optional data.
New automated files require the release introducing this feature. Earlier app
versions may drop the fields; no frozen fixtures or existing studies were rewritten.
No renderer contract or global default was changed.

Tape's signed horizontal pull defaults to zero. It uses continuous deterministic
broad irregular row displacement, canvas-relative distances, subpixel source
sampling and nonwrapping blanking. Its profile clock is separate from the old
held fault clock, so adding pull retains existing tracking/dropout/chroma timing.
Zero pull preserves the old path exactly, including its neutral early return.
**Clean pull / animate** was appended after all prior Tape presets to preserve
their numeric indices; it zeros old faults, enables Mix, and keeps pull zero.
Since 0.5.2, new clean passes use **Pull edges → Keep canvas filled**; the earlier
displacement remains available as **Allow blanking**. Tape damage gained independent
instances in 0.5.1, and Command-D gesture/section duplication shipped in 0.5.3.

## Validation and independent example

Tests run in fresh bounded processes using `.venv/bin/python -m pytest`:

- `tests/test_synth_automation.py tests/test_synth_automation_video.py`: 26 passed.
  Covers endpoints/zero stages, a six-FPS frame-grid endpoint sweep, validation,
  bounds/disabled identity, conflicts, animated cue-base preservation, loops,
  resize/reorder/duplication, repeated 256-event imports, generated v2 pixels,
  save/reload, snapshots, Studies, video/effect clocks and actual MP4 export.
- `tests/test_synth_tape.py`: 11 passed, including signed/broad deterministic pull,
  source sampling, blank-signal preservation and independent old fault timing.
- `tests/test_synth_automation_ui.py`: 7 passed. Actual visible Animate parenting,
  cancel/apply/edit/conflict/toggle/remove, base restore, dirty/undo/redo,
  effect removal/restoration, selected section/target inactive notice, repeated
  lane dragging/cancellation, viewport containment and 1280×720/1440×900 layout.
- Automation UI plus existing effect removal: 12 passed before the additional
  target-warning test. Existing compact workspace/timeline/diagnostics: 18 passed.
  Current automation UI plus diagnostics: 14 passed. Existing effects editor
  integration: 7 passed. Timeline loops/resize/reorder: 45 passed.
- `tests/test_synth_sequence.py tests/test_synth_retime.py tests/test_synth_timeline_loops.py`
  plus the initial automation suite: 54 passed.
- `tests/test_synth_baseline.py`: 12 passed, covering 121 frozen render cases and
  asset identities, with unchanged fixture files. Parent independently repeated
  this gate and got the same result.

The reproducible creator is `scripts/create_timed_automation_demo.py`. The portable
composition is committed at `examples/timed-tape-pull.nebula.json`. Local review
media is in `.validation/timed-effect-automation/`: the composition, detailed
sequence, sampled PNGs and `timed-tape-pull.mp4` (720×480, 15 FPS, exactly 10s,
150 frames confirmed with ffprobe). It has one uninterrupted ten-second portrait
section and only a `tape.pull` gesture from 4–5s, rising in .15s and recovering in
.85s. CRT/portrait settings remain the base. The creator checks full-canvas and
360px before/after identity and visible changes during the gesture. User files
are neither read nor modified. MP4 validation decodes a real export and compares
its gesture frame against automated and plain rendering.

The parent independently verified the native isolated-window workflow: visible
Animate, typed Start 4 / Rise .15 / Hold 0 / Recover .85 / Amount .35, Apply,
scrub at 4.2s with effective-value diagnostics, visible unclipped lane, Undo back
to the clean original, and Redo to the same event. The composition retained one
10s section and the compact viewport. This isolated review preceded the 0.5.0
release and installation noted above.
