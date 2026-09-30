# Effects editor UX

Status: planned, implementation starting 2026-09-30.
Base: 4ba6a63 on codex/studio-editing-library (draft PR #9, itself based on #8).
Delivery branch: codex/effects-editor-ux. Version remains 0.2.0.

## Goal and invariants

Make applying and adjusting effects quick to understand while preserving the
terminal visual style and every existing Study's rendered result. The current
Refined Signal panel has nine applied entries and places its first parameter
722 px down a 750 px inspector. Four inspected studies have parameter pages
between 2291 and 3471 px tall.

Keep renderer algorithms, processing order, defaults, source/effect clocks,
export behavior, section loops and all existing parameter IDs/values intact.
No layer system, draggable effect execution order or blanket More/Fewer switch.
UI navigation/search/inspection must not dirty a document. All authored edits
remain undoable and survive save/load. Do not replace pixel baselines.

## 1. Focused effect editor

Separate the applied-effect overview from editing one effect. The overview
shows active/intermittent/bypassed entries, with sources distinguished from image
treatments. Selecting an entry opens a focused editor immediately; an explicit
Back to effects action returns to the overview. Keep selected effect, scope and
navigation above the parameter scroll. Effect navigation must not contribute a
full rack's height above the first parameter. Switching an effect resets its
parameter scroll; ordinary edits preserve it. Reach all controls at 380–490 px
inspector widths and 720–900 px window heights.

Retain useful Look/Timing/Region/Polarity/Signal/Screen subdivisions and named
groups. Keep group navigation and search accessible without scrolling back to
the top. Do not hide controls behind an undifferentiated advanced switch.

## 2. Editing scope and inheritance

Use a persistent, explicit Editing: Whole clip / Section N — Name header.
Section selection and whole-clip selection must stay synchronized with the
existing timeline. Shared ink timing, master and source-video controls clearly
state that they affect the whole clip, regardless of the selected section.
Show local, inherited whole-clip and study values distinctly. Global edits must
not imply they overwrite explicit section settings. Preserve scope while
navigating overview, library, parameter groups and Object controls.

## 3. Animated versus fixed values

Extract the shared EffectParameter widget into its own module (re-export from
synth_effects_ui for existing imports). Replace the clickable numeric range
that silently freezes at its minimum with a clear read-only animation range and
an explicit Use fixed value action. The proposed starting value is displayed
before applying; never silently claim it is the current playhead value. Existing
fixed controls remain directly editable. Restoring removes only that parameter's
local override and follows the whole clip/study again. State labels and actions
must work for numeric, choice, artwork and text values and preserve hidden
numeric precision when merely focusing/blurring controls. Opening/navigating
must never commit an animated range or unapplied wording.

## 4. Effect discovery and bypass

Add a searchable, categorized Add effect dialog with descriptions, compatibility
filtering, preset selection and an explicit Add action. Inspecting candidates
never changes the document. Treatment categories should be plain and visual
(e.g. Distortion, Texture, Light & color); source families belong to Object and
have a clearly separate route. Adding applies the existing preset semantics
in the selected scope; duplicates are inspected rather than silently replaced.

Give applied image effects an immediate bypass action. Persist bypass separately
from authored activation mode and parameter values, so resuming an intermittent
study effect restores its original timing, including after save/reopen and undo.
An optional boolean `bypassed` entry may be added to effect overrides; absent
means the existing behavior, false can explicitly resume an inherited bypass.
Normalization/merge/compiler must preserve this meaning and reject invalid data.
Do not add bypass fields to untouched documents. Keep bypassed effects visible
and editable; distinguish them from effects absent from the study. Cover local
bypass, inherited global bypass, section resume, parent changes and source-family
compatibility. Compiled off behavior should use the existing effect-off logic.

## 5. Controls and precise actions

Improve presentation metadata independently of rendering values. Keep two
visible decimals, add units only where semantics are known, and use a small
visual hue swatch beside supported hue controls. A swatch is a hue indication,
not a claim to show final composited color. Display animation/inheritance state
compactly, with descriptions/tooltips carrying longer explanations. Keep scroll
wheel edits disabled on closed dropdowns and number controls.

Use clear Restore this effect / Follow whole clip or study actions, plus explicit
preset replacement wording. Replace the generic top-level Reset controls action
with a contextual label whose operation matches the current panel: effect,
object, finishing, master or shared timing. Never silently clear unrelated tabs.
Maintain source/object editing as a distinct action from adding image effects.

## Delegation and ownership

- GPT-6.1 Sol, core: synth_effects_ui.py, synth_composer_ui.py, synth_effects.py,
  synth_subject.py as needed, and new focused core UX tests. Own focused editor,
  scope, bypass, contextual restore and integration of the browser/widget APIs.
- GPT-6.1 Sol, parameters: synth_effect_parameter_ui.py, a new presentation-only
  metadata helper if needed, and new focused parameter tests. Own explicit
  animation/fixed flow, provenance labels, units and hue swatches.
- GPT-6 Luna, library: new synth_effect_catalog.py / synth_effect_browser.py and
  focused library tests. Own categories, search, compatibility, preset choice and
  keyboard-accessible dialog. No edits to shared EffectsPanel or compiler.
- Root: documentation, synth_studio.py embedding/header integration, review,
  shared-test adjustments, final verification, commits, packaging and PR.

Agents share this checkout. No branch switches, commits, pushes, builds, restart
or edits outside the assigned files. Signal contract for library:
EffectBrowserDialog(allowed_effects=None, applied_ids=(), parent=None),
effectRequested(str effect_id, int preset_index), objectRequested(),
set_context(allowed_effects=None, applied_ids=()). Explicit Add emits and caller
resolves/applies against current scope; the dialog does not mutate compositions.
Parameters retain changed/reset signals and refresh(bounds,fixed,inherited,
available), extending with optional keyword context only when coordinated.

## Validation and delivery

Measure first-control visibility and pinned header behavior on real Qt widgets
at narrow/wide inspector sizes. Inspect screenshots for Refined Signal,
Doryphoros, Mixed Media and text, plus video-only effect availability. Exercise
search/filter, keyboard Add/Cancel, bypass/resume, scope changes, reset isolation,
parameter provenance and fixed/animated transitions. Check pending text handling.
Run focused tests per package, then the integrated editor/browser/preview/timeline
suite and frozen Study pixel suite. Include exact bypass resume pixel equality
through save/load/undo and unchanged navigation documents.

Commit packages separately, push a feature branch and open a draft PR stacked
on #9 unless that dependency has merged. Do not merge or tag. Build and verify
the Mac app. Install only when the running app is closed; do not force-quit or
assume permission to discard current unsaved work. Record native automation
limitations honestly if the computer-control runtime remains unavailable.
