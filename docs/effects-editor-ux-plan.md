# Effects editor UX

Status: implemented and packaged 2026-09-30; merged into main and installed on 2026-10-01.
Base: 4ba6a63 on codex/studio-editing-library (draft PR #9, itself based on #8).
Delivery branch: codex/effects-editor-ux. Milestone version: 0.2.0.
This records the original milestone. Current workflows are in [README](../README.md).

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
- Library agent (reused idle reviewer): new synth_effect_catalog.py / synth_effect_browser.py and
  focused library tests. Own categories, search, compatibility, preset choice and
  keyboard-accessible dialog. No edits to shared EffectsPanel or compiler.
- Root: documentation, synth_studio.py embedding/header integration, review,
  shared-test adjustments, final verification, commits, packaging and PR.

A new GPT-6 Luna library agent was requested, but the chat reached its agent-thread
limit. The idle review agent was reused for that bounded task instead.

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

## Delivery notes

All five items are implemented. The focused editor keeps navigation and scope
above a bounded parameter scroll. Activation and preset replacement have their
own named disclosure inside that scroll. Arrange has a separate bounded view
and returns to the previous effect, scope and scroll position. The overview
routes source rows to Object; the library lists compatible image treatments.

Bypass retains authored activation and settings, including intermittent studies
and inherited section behavior. Shared ink clocks ignore presentation bypass so
section duration cannot change accidentally. Contextual restore affects only
the current panel; source reset retains the imported file and In/Out trim.

Parameter widgets retain drafts in their original section. Save validates and
commits hidden drafts together. Drafts for removed sections stop participating
in Save, while Undo can restore them. Conflicting drafts for one scope block
Save with an explanation. Text-source changes preserve wording without
re-enabling the old source.

Themed screenshots at 1280×800 use a 391×605 inspector, with 245–260 px for the
parameter viewport and the first control at y347–362. Narrow 380 px inspectors
and 1280×720 windows are covered; Arrange remains scrollable at both 720 and
800 px heights. Inspection caught and fixed clipped inactive numeric fields.
Review captures and measurements are in the ignored output/effects-ux-final
folder. These are offscreen Qt checks; native Mac interaction automation was
unavailable in this session.

Validation completed before delivery:

- Frozen study pixel contracts: 12 tests passed, covering 121 render scenarios
  and bundled model identity; no baseline updates.
- Bypass/shared-timing gate: 16 passed, including saved/reopened resume pixels
  and identical section durations while timing controls are edited.
- Parameter, widget, core and window/save gate: 55 passed after the themed
  numeric sizing fix. Arrange delta: 5 passed; scoped window/save checks: 6 passed.
- Integrated gate: 365 passed; two assertions depended on the old widget layout
  (dictionary row order and direct-page hidden state). Updated them to check the
  actual bottom visible control and hidden Object tab. Final 52-test gate passed
  in 194.75s, covering both assertions, scoped save/window integration, all
  parameter UX checks, core bypass/navigation and the final Arrange changes.
- macOS build and deep strict code-signature verification passed. Version
  metadata remains 0.2.0; no merge, release tag or version bump.

Commits are split into planning/extraction, discovery, persistent bypass,
parameter UX, numeric sizing, focused-editor integration and documentation.
The feature branch is stacked on draft PR #9. The installer refuses to replace
an app that is still running; no force quit or composition backup was performed.

PRs #8, #9 and #10 were merged into main in dependency order on 2026-10-01.
The merged source matched the tested feature branch. The Mac app was rebuilt
from main, installed in ~/Applications and launched; strict signature verification
passed and no new startup traceback was logged. The previous app bundle was
preserved by the installer. Version remains 0.2.0; no release tag was created.
