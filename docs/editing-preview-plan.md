# Editing and preview improvements

Status: planned; no implementation started.
Prepared: 2026-09-30.
Repository: AlanFnz/nebula-pipeline.
Baseline: main at 167636b; the separate playback-icons change is dee20f4 / PR #8.

## Outcome and scope

Make the existing Studio easier to edit, safer to leave, and quicker to preview.
This milestone covers everyday editing and preview responsiveness. Preserve the
terminal visual style, the single toggling playback button, and approved Study
pixels. Layers, new effects, timeline split/copy tools, and the visual Study
browser are subsequent milestones, not dependencies of this work.

Deliver four separately reviewable changes, in the order below. Do not change
rendering algorithms, recipe defaults, source/effect clocks, export FPS, or
saved composition schemas to implement editor behavior. Preview preferences
belong in workspace settings, not artistic documents.

## Current implementation

- `synth_studio.py` owns document operations, composition history, transport,
  foreground rendering and full-loop preparation. The main synth editor does
  not currently register the common editing/transport shortcuts.
- Unsaved detection compares content with a deep saved snapshot, includes
  unapplied text, and guards close. New/Open/Study loading can still replace an
  edited document without this guard. Save always opens a file chooser.
- Successful asynchronous Study saves have document-identity and clean-revision
  guards; keep these protections when adding file identity.
- `synth_preview.py` stores RGB frames by output-frame number under a 192 MiB
  LRU budget. Every `invalidate()` clears all cached frames.
- `PreparePreviewJob` takes immutable settings snapshots and owns its video
  provider. The foreground job uses a separate provider. Preview/export share
  the renderer; export never reads preview frames.
- `synth_composer_ui.py` owns section selection, repeated occurrences, dragging
  and resizing. Selection identifies source sections; repeated views refer to
  the same authored section.

## 1. Document identity and safe replacement

User behavior:

- Show the composition name and a visible unsaved indicator in the header and
  native window title. Keep detailed-copy windows distinguishable.
- Save writes to the current user document. The first save asks for a location.
  Save As always asks and updates the associated path only after success.
- A built-in Study, imported clip, new composition, or detailed copy has no
  associated writable file until explicitly saved. Never overwrite bundled
  Study assets or source video through Save.
- Reuse Save / Don't Save / Cancel for New, Open, Load Study, preset replacement,
  and a new imported-video document, as well as window close and app quit.
- Cancelling either dialog, invalid text, or a failed write leaves the current
  document, undo history, path, selection and working preview intact.
- Undo back to the saved content clears the unsaved indicator. Unapplied text
  updates it while typing. View zoom, scrubbing, selection and preview settings
  are editor state and do not dirty the composition.

Implementation:

- Extract a small document-session helper if it reduces the responsibilities in
  `synth_studio.py`: associated path, document identity, saved snapshot/revision,
  display title and one replacement guard. Avoid a broad window rewrite.
- Keep loading and replacement transactional: validate the proposed document,
  obtain any required save decision, then install it. Failed/cancelled Open does
  not reset history or cancel the current document's workers.
- For asynchronous video imports, prepare first and guard the final replacement
  against the current content, including edits made during preparation. An
  import launched for a different document identity cannot replace a later
  document. Relinking remains an undoable edit, not a new-document replacement.
- Capture focused numeric edits before saving/replacement. Preserve existing
  text validation and conflict handling. Cancelled replacement must not destroy
  drafts; normal focus-loss numeric commits remain undoable edits.
- Write JSON atomically using a temporary sibling and replace after successful
  serialization/write. Failure must preserve the existing file and save path.
- Keep Study-save clean-revision rules. Export never establishes a saved
  document baseline. Save As Study never silently binds Save to a library file.
- Update dirty/title state from edit/load/save/undo and text signals; avoid
  serializing large artwork documents on a rapid polling timer.

Acceptance checks:

- Compose, sequence and preset documents: first Save, repeated Save, Save As,
  canceled dialog, invalid draft and failed write.
- Replacement through every user entry point, including delayed import results.
- Newer saves/documents cannot be marked clean by an older background save.
- Save/close cancellation preserves workers and sources. No media is overwritten.

## 2. Keyboard controls and discoverability

Use common window-scoped actions, with menu entries/tooltips showing shortcuts.
The window containing the focus owns the action, including detailed copies.

| Shortcut on Mac | Behavior |
| --- | --- |
| Space | Toggle playback when focus is in the viewer/timeline or neutral chrome |
| Left / Right | Pause and step one output frame in the viewer/timeline |
| Shift + Left / Right | Pause and step ten output frames in the viewer/timeline |
| Command + S | Save |
| Command + Shift + S | Save As |
| Command + O | Open through the replacement guard |
| Command + Z | Composition Undo, unless an editor owns a local undo operation |
| Command + Shift + Z | Composition Redo, unless an editor owns local redo |

Use Qt standard key sequences for platform equivalents. Preserve ordinary
Space/arrows/undo inside text editors, spin boxes, sliders and popup controls.
Do not bind Space globally in a way that also activates a focused pushbutton.
Escape continues to cancel timeline drags/resizes and dialogs. Frame stepping
clamps to valid bounds; playback retains its existing loop behavior.

Do not pretend the detailed sequence/preset editor has composition history.
Disable document undo/redo there while retaining widget-local undo and all
applicable saving/transport shortcuts. Adding detailed-editor history is later.

Acceptance: keyboard vs mouse behavior agrees; text edits, numeric stepping,
slider arrows, modal dialogs and multiple windows keep their expected routing.
Scrubbing and playback do not add history or dirty the document.

## 3. Automatic preparation and preview scope

User behavior:

- Keep one play/pause toggle. Add a compact preview scope: Entire timeline or
  Selected sections. Scope and preparation do not edit or loop the document.
- Show a thin cached-range strip aligned with the timeline, plus concise states:
  Updating, Preparing, Ready, or Limited by rendering. Preserve the displayed
  measured preview FPS vs target/export FPS distinction.
- Automatically warm a small neighborhood after editing/scrubbing settles.
  Keep an Auto prepare toggle in preview settings, and an explicit Prepare
  preview action for the active scope. Never start playback simply because
  preparation finishes.
- Whole timelines longer than the memory budget still play and warm a bounded
  window. An oversized request must not require caching the whole composition
  before any useful work happens; explain when only part fits.

Selection semantics:

- Selected sections means the selected section IDs, traversing their rendered
  occurrences in timeline order, including existing authored repeats. Display
  the occurrence count/duration so repeated sections are not ambiguous.
- For nonadjacent selections, skip unselected intervals during preview only.
  Render with original absolute timeline frame numbers: source video, noise,
  transitions and effect clocks must match full-timeline playback and export.
- Preserve seeking to a clicked repeated occurrence. Frame stepping while scoped
  follows the selected occurrence list. Switching scope/selection pauses and
  retains the current frame if valid, otherwise seeks to its first valid frame.
- Store resolved scope as frame intervals using existing duration/frame rounding;
  do not duplicate, trim or recompile a shortened artistic composition.

Scheduling and resources:

- Put scheduling/cache planning in a focused helper instead of adding another
  independent queue to the window. Foreground frame requests always take
  priority over warming. Start with ~400 ms idle debounce, ~2 seconds ahead
  and ~0.5 seconds behind; cap by frame memory and tune using measurements.
- Use short bounded batches and backpressure so queued Qt frame signals cannot
  temporarily hold an entire long clip outside the cache budget. Limit worker
  concurrency; never use one video provider concurrently from several workers.
- Stop obsolete work at frame boundaries on edits, seeks, scope changes, load,
  close or export. Pause warming during export. Do not let cancelled jobs
  repopulate cache or update progress for the next document/generation.
- Avoid a refill/eviction loop when the requested scope exceeds RAM: schedule a
  stable bounded window and move it with the playhead. Keep the current frame
  available. If a frame itself cannot fit, show that limit and remain usable.
- Foreground rendering may still need to finish an in-flight expensive frame;
  no promise of instantaneous cancellation or full-resolution real-time playback.

Acceptance: absolute-time parity for selected sections and repeated occurrences;
no automatic playback; responsive foreground seeks; bounded memory including
pending deliveries; no idle render churn; clean cancellation and source cleanup.

## 4. Reuse unaffected frames conservatively

Implement this after the new scheduler works with full invalidation. Correct
pixels take priority over reuse. Keep a full-clear fallback for any unclassified
change.

- Maintain two separate concepts: worker generation rejects stale results;
  render validity determines whether an already cached frame can be retained.
  Carry validated retained frames into the new generation explicitly.
- Preserve cache for editor-only actions such as selection, view zoom and
  preview-scope changes when render inputs are unchanged.
- Start incremental invalidation with section-local visual parameter edits only.
  Require unchanged timeline structure, frame rate, clocks and global inputs.
  Compare compiled states/cues, not just the UI action name or section label.
- Invalidate every occurrence using a changed state, including repeats and any
  transition interval that consumes that state as its previous or next state.
  Account for cue boundaries and morph dependencies into neighboring sections.
- Master/global changes, canvas/quality changes, source/relink changes, seed or
  renderer changes, duration/retime changes, reorder and loop changes clear all
  frames initially. This avoids unsafe reuse after absolute-time shifts.
- Cache validity includes source/proxy identity and file fingerprint, preview
  dimensions, source-only bypass state, and all relevant rendering settings.
  A replaced or unavailable source cannot leave an apparently valid old preview.
- Never reuse a cached preview as export data or change rendering to obtain a hit.

Acceptance: compare retained and rerendered RGB frames with fresh rendering at
boundary, interior and repeated times. Verify a local edit reuses genuinely
unaffected frames and rerenders dependent transitions. Test every fallback and
stale callback after replacement, undo and source changes.

## Validation and delivery

- Extend behavioral tests near `test_synth_unsaved.py`,
  `test_synth_preview_ux.py`, `test_synth_timeline_loops.py` and composer/editor
  fixtures. Test meaningful user decisions, async races and cache parity rather
  than private implementation shapes.
- Keep frozen Study pixel manifests unchanged. Run representative reference,
  profile, mixed-media, text and video parity checks, including loop/retime and
  source-only previews; run established broader gates once for the integrated
  result. No regenerated baselines to conceal differences.
- Measure the same local clips before/after at 360 px and 720 px: edit-to-current
  frame latency, seek latency while warming, cached playback cadence, rendered
  frame count after a local edit, and peak memory. Report measured results;
  do not invent a universal FPS/speedup target.
- Exercise real Mac menus/shortcuts, multiple windows, Save/Cancel/Don't Save,
  selected playback, repeated occurrences, reopen and export. Existing headless
  tests supplement this; they do not replace native interaction verification.
- One atomic commit per work package, followed by a focused integration-fix
  commit if needed. Push a feature branch and attach a reviewable PR with exact
  validation results. Update README and CHANGELOG for delivered behavior.
- Preserve the separate playback-icon work in PR #8. Check its current status
  before branching: use main if merged, otherwise base the work on its commit
  and document that dependency. Do not merge or retag as part of execution
  without the user's instruction. Version remains 0.2.0 until a release task.
- Rebuild/sign/install the Mac app after verification. The previous icon build
  is ready but not installed: computer-control startup failed and the user has
  not yet confirmed closing Studio. Recheck this at execution time; preserve
  any current work and do not force-quit to install.

## Execution handoff

The requested execution model is `gpt-6.1-sol`, exposed by this session's
subagent tool. A root agent can delegate implementation to it after this plan
is reviewed; the user can alternatively switch the main chat model.

Prefer one executor for document operations and preview integration because
both edit `synth_studio.py`. A second agent may review cancellation/cache
correctness or implement an isolated helper with explicit file ownership.
Avoid concurrent edits to the main window. The root retains integration,
native verification, packaging and reporting responsibility.

Start by checking the actual branch, working tree and PR #8 state, then record
baseline measurements and deliver package 1. Complete and review each package
before moving on. Report any necessary adjustment to scope instead of silently
introducing layers or renderer changes.

## Later roadmap

1. Timeline editing: duplicate/delete/rename, split semantics, effect copy/paste,
   and timeline zoom, all with loop/retime-aware undo.
2. Visual Studies browser: thumbnails, favorites and categories; effect presets
   reusable independently of a whole Study.
3. Layers: treated video plus independently animated text first, then opacity,
   transforms and per-layer timing/effects with master adjustments after the
   composite. Existing Studies require a pixel-preserving single-layer adapter.
