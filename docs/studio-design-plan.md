# Studio interface redesign

2026-10-10 · Approved direction: Studio

## Outcome

Make Nebula a calmer, more legible creative workspace while keeping its
phosphor identity. Use neutral charcoal surfaces, off-white labels, restrained
green accents, compact parameter rows, and a simpler inspector. Apply the same
visual system to Studies, effect discovery, automation and ordinary dialogs.

The approved conversation mockup is a direction, not a replacement application:
retain the real app's complete controls, source types, scope rules, accessibility,
keyboard shortcuts and accurate preview/export status. Rack is an alternative
explored in the proposal, not a second workspace to implement in this release.

## Boundaries

- Presentation only: no renderer, effect mathematics, saved composition schema,
  Study settings, defaults, timeline timing or source behavior changes.
- Preserve explicit clip overrides, project versus clip scope, effect instances,
  automation, text drafts, undo/redo and removal semantics.
- Preserve saved window geometry, splitters and deliberate numeric zoom. Fit
  remains an explicit automatic mode; do not force it over user preferences.
- Keep Add, Bypass/Resume, Remove, Restore and automation discoverable. Compact
  does not mean hiding essential controls or reducing interaction targets.
- Display precision and any existing percentage conversions remain lossless.
  Do not introduce a new unit conversion in a visual redesign.

## Work packages and ownership

### 1. Shared visual system — GPT-6.1 Sol

Own `studio_theme.py` and theme assets only. Define semantic colors for canvas,
panel, raised input, border, readable text, muted text, selection, accent, focus,
disabled, warning and destructive states. Keep existing public color names for
custom-painted widgets. Replace green outlines with quiet neutral separation;
use green for selection and primary actions. Use small consistent corner radii,
clear keyboard focus, consistent fields/tabs/buttons, and unobtrusive scrollbars.
Use a native sans-serif UI font and retain a monospace helper for values and
timecodes. Cover dialogs, menus, tables, lists, Studies, discovery and automation
through the shared theme; maintain readability rather than blanket miniaturizing.

Acceptance: no style parser errors; enabled/disabled/hover/focus/selected states
are distinguishable; primary actions retain contrast; all current theme callers
continue working. Verify affected theme/widget tests.

### 2. Compact parameter controls — GPT-6.1 Sol

Own `synth_effect_parameter_ui.py` and dedicated parameter UI tests. Put normal
numeric labels, slider, value and reset in a compact responsive arrangement.
On narrow inspectors allow a second row rather than clipping. Give choice
fields enough width for meaningful labels. Preserve full-size text/artwork
editors and read-only animated ranges, fixed-value conversion and draft state.
Suppress repetitive ordinary project provenance while keeping explicit
animation, local overrides, inherited values and unavailable states legible;
retain full explanations in accessible descriptions/tooltips. Integrate the
existing automation action without an unnecessary full-height row per control.

Acceptance: 380/490/650 px inspector widths have no clipped controls; sliders
still update on release; typed precision, reset, automation signals and text
drafts survive refresh/scope changes. Run parameter and relevant integration
tests, adding only behavioral/layout regressions needed for the change.

### 3. Inspector hierarchy and effect navigation — GPT-6.1 Sol

Own `synth_effects_ui.py` and dedicated effects layout tests. Consolidate editor
navigation/action rows, keep the effect's identity prominent, reduce ordinary
status verbosity, and preserve actionable diagnostics. Make logical parameter
groups collapsible with search that reveals matching controls. Keep existing
group/tab filters, creative controls, activation/preset editing and every source
path reachable. Preserve project/clip separation and the overview list; do not
introduce drag-to-reorder effects or imply an order the renderer does not use.

Acceptance: Add, Remove, Bypass, Add instance and Restore remain accessible;
search, diagnostics and deep links reveal their targets even in collapsed
groups. Scope changes do not silently author values. Validate editor, scope,
instances, discovery and compact effect tests.

### 4. Workspace integration — root agent

Integrate the new hierarchy into the shell. Make global actions, canvas and FPS
readable and compact. Prefer the monitor in the default split while preserving
saved splits. Keep zoom/comparison/snapshots/full screen convenient. Consolidate
transport and quality where it fits; make preparation coverage subordinate to
the playback scrubber and explain it clearly. Keep actual versus target FPS,
prepared count, export progress and cancel behavior intact. Update custom paint
colors and numeric typography to use the shared system as needed.

### 5. Review, documentation and release — root agent

Review each package's diff and integrate without overlapping file ownership.
Validate representative footage, generated objects and text; inspect Studies,
effect browser and automation dialogs. Check native macOS and offscreen
1280×720, 1440×900 and 1728×1017 layouts, including a narrow inspector and
restored splits. Compare render baselines to confirm artwork is unchanged.
Use focused test groups in fresh processes where Qt accumulated-window overhead
makes a giant combined run unhelpful. Update user documentation only where the
workflow changed. Record results and limitations in a delivery note.

Create atomic commits, review the final diff, update version/changelog using
the repository convention, push and merge through a PR. Build and verify the
macOS bundle, close the running app gracefully, install and reopen it. Preserve
the current document; never dismiss an unsaved-changes prompt destructively.
Merge and installation are already authorized by the user.

## Execution order

1. Commit this plan, then implement packages 1–3 concurrently with disjoint files.
2. Root integrates workspace changes while the agents work.
3. Review agent work, resolve layout/interaction issues, inspect native UI.
4. Run the appropriate UI and rendering checks; document actual results.
5. Release, merge, install and verify the installed app.
