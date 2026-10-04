# Timed effect automation

Prepared: 2026-10-04. Baseline: main `5ded876`, Nebula Studio 0.4.4.
Executor: GPT-6.1 Sol. Integration and independent review: parent agent.
Branch: `codex/timed-effect-automation`.
Roadmap: [A5 motion controls](creative-controls-audio-roadmap.md).
Status: implemented in the assigned branch; parent owns native review and release.
Delivery: [implementation notes](timed-effect-automation-delivery.md).

## Outcome and acceptance journey

An artist keeps a single ten-second section and its existing look, adds a
horizontal tape pull starting at 4 seconds, lets it peak quickly and settle by
5 seconds. The other nine seconds and the original source timing are unchanged.
The artist can edit this gesture in the Studio without editing JSON or asking
an agent. It saves, reopens, previews, exports and travels with the section.

Automation changes a parameter over time. It is separate from the visual effect
it controls. The authored study, inherited settings and Creative controls remain
the base. Do not bake the study into hundreds of replacement states, split the
section or reset procedural/video clocks to achieve this feature.

## Scope

- One-shot rise/hold/recover gestures on supported continuous numeric image
  treatment parameters, with signed change amount and easing. Several different
  targets and separated events on the same target are supported.
- Section-local events, visible and editable from the parameter inspector and a
  compact timeline lane. When a whole-clip parameter is inspected, explicitly
  choose the target section in the event editor; default to the playhead section.
  The single-section case requires no extra selection.
- A neutral-by-default horizontal pull in Tape damage, suitable for the user's
  VHS example. Existing Tape parameters keep their definitions and defaults.
- Undo/Redo, save/load, studies, snapshots, detailed copies and MP4 export.
- Arbitrary keyframe graphs, audio analysis/routing, multiple audio tracks,
  layer compositing, looping envelopes independent of section loops, automated
  discrete choices/seeds/source replacement, and Master automation are deferred.
- Do not edit the user's saved project as part of this implementation. Its path
  has not been supplied. Demonstrate using an independent local example.

## Architecture and data contract

Read the current implementation and adjacent tests before editing:
`synth_composition.py`, `synth_sequence.py`, `synth_effects.py`,
`synth_creative.py`, `synth_composer_ui.py`, `synth_effects_ui.py`,
`synth_effect_parameter_ui.py`, `synth_studio.py`, `synth_exploration_studio.py`,
`synth_preview.py`, `synth_tape.py`, `synth_retime.py` and the effect catalog.

Create a small independent `synth_automation.py` module for target metadata,
normalization, envelope evaluation and resolved-preset application. Avoid import
cycles: low-level automation may import module parameter definitions, but not
composition/UI. Reuse the same evaluator in preview, diagnostics and export.

### Authored events

Store optional `automations` on each section. Each event has a stable unique ID,
a canonical parameter path, signed `amount`, enabled flag, easing (`smooth` or
`linear`) and normalized section positions for start, attack, hold and recovery.
Keep JSON field names explicit about fractions; present seconds in the UI.
The start plus all stages must fit inside the base section. Each total gesture
must be positive; zero attack/hold/recovery is allowed with specified endpoint
behavior. Validate finite real values and reject booleans masquerading as numbers,
unknown/ineligible paths, duplicate IDs, invalid easing and invalid bounds.
Use bounded list sizes to avoid unbounded work from malformed files.

Normalized positions ensure that resizing a section scales all gesture stages
proportionally. FPS changes leave the continuous curve at the same time fraction;
output simply samples it on the new frame grid. Never quantize the evaluator to
effect cadence or the number of preview frames actually rendered.

Initial conflict rule: reject overlapping enabled intervals on the same target
within a section, with a useful message. Adjacent endpoints and events on
different parameters are allowed. A disabled event is retained and visible;
reenabling must validate conflicts. This avoids an unexplained summing order.

Missing/empty automation must preserve legacy behavior exactly. Do not rewrite
every bundled study, change render versions globally or regenerate baselines.
Document that newly authored automation requires this new app version.

### Compilation and evaluation

Expand section events into optional sequence events with absolute timeline start
and stage durations, following `section_placements()` and each section's internal
loop count. Events repeat for every section/group occurrence, move with reorder,
and scale on resize in both Effects only and Video + effects modes. They must not
inherit a second accidental scale from the procedural `effects_rate` time map.
When a section is duplicated, preserve its gestures and establish valid IDs for
the chosen uniqueness scope. Deleting a section deletes its events.

Apply automation after cue interpolation, inherited/fixed/Creative parameter
resolution and before actual image rendering. At time t:

`effective = clamp(base(t) + amount * envelope(t), parameter min, parameter max)`

The envelope is exactly zero outside its half-open event interval. Smooth uses
smoothstep separately on attack and recovery, with constant one through hold.
At the end it is zero; zero-duration edge stages behave as explicit steps. Skip
zero deltas without any preset normalization/resampling that changes pixels.
Never change module enabled flags or base settings while evaluating automation.
Bypassed/off effects remain off. If an event targets an inactive effect, show why
it has no visible result; do not silently turn that effect on.

Compiled sequence automation must survive `normalize_sequence`, save/load and
the detailed-copy route. `composition_from_sequence` must retain it without
double-applying it. Define and test how imported sequence events are mapped or
retained when its section is looped, resized or reordered. No silent dropping.

### Supported targets

Start with an explicit set of meaningful continuous treatment controls: Tape
horizontal pull/tracking/jitter, Signal drift amount, Signal breakup amount,
Color separation amount, Ghost trail length/brightness, Bloom strength, CRT
capture bend, and representative Raster/grain and Chroma print intensities.
Expand only where semantics are straightforward. Paths use the existing shared
parameter definitions and formatting. All displayed supported targets get an
Animate action; unsupported values do not pretend to support automation.
Exclude timing clocks/rates, cadence, seeds, choices, counts, text/artwork,
dimensions requiring cache rebuild, ink sentinel timings and source replacement.
This is a deliberately bounded first release, not a claim that every numeric
control can already be automated. Record the shipped list in delivery notes.

## Tape horizontal pull

Add a signed continuous pull amount to Tape damage with zero default. Positive
and negative values pull in opposite horizontal directions. Resample the actual
combined picture so that details stretch/shear together with a broad irregular
row-dependent horizontal displacement; do not draw bright rectangles or merely
add a luminous echo. Use deterministic continuous motion, subpixel sampling,
canvas-relative distances and nonwrapping edges. If a secondary shape control is
needed, keep its scope narrow and explain it. Preserve the existing tape faults
exactly when the new pull is zero, including the existing early-return path.

Provide a clearly labelled starting preset for a clean pull: existing faults at
zero, mix on, pull initially zero, so the effect alone leaves the picture intact
until animated. Do not replace an already-used Tape effect's settings when
creating an event. The 4–5s demo should change only this new parameter.

## User experience

### Parameter action and event editor

- Place a compact labelled Animate action near supported parameter controls.
  Show an automation indicator/count and an edit entry for existing events.
  Keep the value field labelled as its base/fixed value; communicate that the
  event adds a temporary change and returns to the moving base.
- Open a compact editor with target effect/parameter and target section named,
  Start, Rise, Hold, Recover, Change amount, Easing and Enabled. Show total event
  duration and a small curve preview. Use wheel-safe controls and existing
  two-decimal/percentage presentation conventions.
- Default start to the playhead position within the chosen base section; use a
  short gesture that fits the remaining section. Offer a useful quick-pull shape
  (short rise, no hold, longer recovery). At a section end, clamp the proposal to
  a valid interval and explain it rather than authoring out-of-range data.
- New/edit changes are a draft until Apply. Cancel/Escape/window close do not
  mutate document/history. Apply creates one undo step. Use frame stepping for
  comfortable input, but retain fractional timing precision in saved values.
- List existing events with Edit, Enable/Disable and Remove; all changes
  undoable. Errors stay in the editor and identify the conflict or invalid stage.
- Effect bypass preserves automation. Effect removal explicitly removes its
  events in the affected scope along with settings; Undo restores both. A preset
  replacement preserves existing events and makes that retention clear.
- Parameter restore restores the base only; automation remains visible and has
  its own remove action. No invisible automation survives a Remove effect action.

### Timeline

Add a slim automation lane below the section blocks, shown only when events
exist. Keep the recent compact workspace: no permanent large panel. Represent
events with their envelope and a readable tooltip (target, absolute time,
section). Multiple targets may share a compact lane; selecting/overlap access
must remain unambiguous through a list/context menu.

Click/double-click to select/edit, context menu to disable/remove, and drag an
event body to move it within its section. Map repeated occurrences back to the
same authored event, showing that a looped event edits all repetitions. Drag
commits once on release; Escape cancels. Do not hijack existing section selection,
resize, reorder or loop hit targets. Expose keyboard-accessible equivalent
editing through an Automations button/list; a painted lane cannot be the only
route. A full curve/keyframe canvas is unnecessary for this milestone.

## Integration behavior

- Feed event edits through existing composition history and preview invalidation.
  Dirty/close guards, A/B snapshots and save-as-study must include them. No stale
  prepared frames after Apply, drag, bypass or remove.
- Frame visibility/diagnostics must resolve automated values at the current
  playhead without claiming an inactive module is visibly active.
- Existing whole-clip versus section effects precedence stays intact. An event
  always belongs to the explicitly named section even when opened from a
  whole-clip base parameter.
- Reuse cached rendering and existing workers. Envelope evaluation is cheap and
  should not rebuild source media/proxies. No new background render worker pool.
- Keep the pending audio roadmap compatible: audio can later add modulation at
  the same well-defined evaluation point, but no audio machinery is added now.

## Work sequence and ownership

1. Parent commits this plan. Sol reads it and inspects current code, then builds
   normalization/evaluator plus tests; commit one coherent engine change.
2. Sol adds neutral tape pull and validates identity at zero and deterministic
   visible displacement; separate effect commit.
3. Sol wires parameter editor, event dialog/list, timeline lane and history;
   separate UI commit(s), following the above semantics.
4. Sol supplies focused tests and a standalone demo at 4–5s in one ten-second
   section. Update README, roadmap A5 status and implementation delivery notes.
   Do not mark deferred arbitrary keyframes/audio done.
5. Parent independently reviews the implementation, handles integration defects,
   checks native UI, releases, merges and installs under standing authorization.
   Sol must not push/merge/install/restart the user's app. Avoid modifying files
   concurrently with parent; report changed areas and commit hashes.

## Validation gates

- Unit: precise attack/hold/recovery/endpoints, smooth/linear, zero stages,
  validation failures, bounds clamping, disabled identity, overlapping rules.
- Base preservation: resolve before/during/after an event; only its target
  changes, including against an animated study base. Outside 4–5s the demo must
  be pixel-identical to the same composition without automation.
- Arrangement: section loops, multi-section group loops, reorder, duplicate,
  deletion, proportional resize, effects/video clocks, FPS changes, source
  sequence automation round-trip and no double application.
- UI: apply/cancel/edit/remove/disable, dirty state, one-step undo/redo, effect
  removal and restoration, drag cancellation, selection of repeated occurrences,
  narrow window, event-list accessibility, no false inactive/animated labels.
- Persistence: save/reload, snapshots, save-as-study, compiled detailed copy;
  compare resolved values and rendered frames after every round-trip.
- Rendering: frozen baseline fixtures unchanged, full-canvas and 360px renders,
  sequential playback versus random seeks deterministic, exported MP4 includes
  the gesture and has the original duration/FPS. Reuse existing export pathway.
- Native QA: verify the artist can add a 4s-start/1s-duration pull while keeping
  one section. Verify the monitor retains its compact layout at 1280×720 and a
  normal desktop size. Do not alter the user's current composition for testing.
- Run UI tests in bounded fresh processes; a previous very long combined Qt run
  accumulated widgets and became slow inside stylesheet updates. Run appropriate
  targeted groups and frozen baselines, not endless redundant checks.

Write delivery notes with actual tested behavior, controls, limitations, test
commands/results and demo paths. Record any design deviation and rationale.
