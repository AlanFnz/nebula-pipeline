# Visual effect discovery implementation plan

Prepared: 2026-10-02.
Status: implemented on the feature branch for draft review; see [delivery notes](visual-effect-discovery-delivery.md) for validation and native adjustments.
Executor: GPT 6.1 Sol.
Baseline: `main` at `578411a`, released and installed as Nebula Studio 0.3.0.
Working branch: `codex/visual-effect-discovery`.
Parent roadmap: [creative controls and audio reactivity](creative-controls-audio-roadmap.md).

## Outcome

Help an artist understand what an effect contributes, try it on their own material,
and deliberately apply it. The acceptance journey is to start with a shape,
audition two treatments, keep one, understand why another treatment has little
visible impact, and inspect how an existing study creates its look.

Deliver A4: effect and preset auditions, useful visibility explanations, and an
editable breakdown of the current piece. Preserve the terminal appearance and
the space available to the monitor. A1 starting points, A2 Creative controls and
A3 snapshots and variations are already available in 0.3.0.

This document makes implementation decisions rather than leaving a list of UI
possibilities. Small implementation adjustments are acceptable when backed by
code inspection or native UI testing. Record material deviations and their
reason in the delivery notes.

## Scope and boundaries

- Support the existing compatible image treatments and their existing presets.
  Text, shapes, rays, stamps, silhouettes and particles remain Object sources.
  Do not turn them into duplicate entries in Add effect.
- Extend Add effect and the existing inspector preset workflow. Reuse the
  composition compiler, renderer, transport and preview cache.
- Add presentation metadata and temporary editor state. Applying an effect uses
  the existing composition schema; browsing adds no saved fields or assets.
- Preserve existing studies, preset values, render versions, random seeds,
  source framing, Timeline FPS, shared ink timing and section durations.
- Motion envelopes, audio, word morphing, layers, arbitrary effect order, new
  rendering algorithms and more Creative controls are separate milestones.
- Do not change the installed app during implementation. Finish with a tested
  feature branch and draft PR; merging, release versioning and installation are
  subsequent tasks. The current request authorizes this plan only.

## Existing code to build on

| Area | Current implementation and implication |
| --- | --- |
| Discovery | `synth_effect_catalog.py` has presentation metadata and source compatibility filtering. `synth_effect_browser.py` has search, categories, presets and explicit Add or Inspect actions. Browsing currently emits no edit. |
| Effect editing | `EffectsPanel` in `synth_effects_ui.py` owns the overview, inspector and preset actions. `CompositionPanel.change_effect()` in `synth_composer_ui.py` commits edits to the selected scope. |
| Preset semantics | `effect_preset()` in `synth_effects.py` supplies fixed parameter defaults and preset values. `EffectsPanel.apply_look()` preserves a local bypass flag and neutralizes inherited Creative adjustments when replacing a section preset. Add and replace are currently distinct paths. |
| Compilation | `compile_composition()` resolves source states, sections, inheritance and creative adjustments. `merge_effects()` combines global and local entries. Whole-clip edits do not override explicit section edits. |
| Current status | `describe_effects()` summarizes activation and ranges across states. It does not establish perceptual visibility at the current frame. Some treatments, such as Ghosts, span more than one module. |
| Frame evaluation | `render_sequence_frame()` in `synth_sequence.py` resolves cue transitions and effect/video time maps. Diagnostics must agree with this path, including morph, sweep and flash behavior. |
| A3 preview | `ExplorationStudio` routes `preview_sequence()` and `preview_document()` independently of the working/export sequence. `begin_comparison()` supports temporary candidates, but `audition_pending()` currently classifies every candidate as an unsaved variation. Discovery needs a distinct lifecycle. |
| Scheduling | `synth_studio.py` owns foreground rendering and cancellable preparation. `synth_preview.py` provides scopes, validity and scheduling. `ComparisonFrames` shares one 192 MiB frame budget across A/B banks and pending reservations. |
| Study presentation | `synth_studies.py`, `synth_starters.py` and `synth_studies_ui.py` handle studies. `synth_study_thumbnails.py` already has separate cancellable background thumbnail work. Coordinate with it; do not add competing thumbnail workers. |

Read these files and their adjacent tests before implementation. Recheck repository
status and applicable instructions; do not reset unrelated work or rebuild an
already completed milestone.

## User experience

### Browse and audition an available effect

Open **Effects → Add effect…** in the current editing scope. Keep search,
categories, the selected effect's explanation and its Starting preset choice.
Display the target explicitly, such as **Whole clip** or **Section 02**.

Use a compact window-modal browser positioned over the inspector, leaving the
monitor visible. Aim for 380–460 px width, with a scrollable list/body and pinned
actions. Fit within the available screen height at 1280×720. Do not add another
permanent column or shrink the monitor to accommodate preview thumbnails.

Selecting an available effect or changing its preset requests a still preview
after a short debounce, initially 300 ms. Only the selected candidate renders.
The main monitor displays **Preset preview · effect / preset** while the browser
offers **Before / Preview**, **Play preview**, and a short preview scrub control.
The before image is the complete current composition, including its existing
treatments. It is not the untreated source.

Playback is opt-in. Show the first useful frame promptly; prepare a short loop
only when Play preview is requested. Display loading, current sample time,
preview resolution and errors clearly. Clear or visibly mark an obsolete image
while the next selection is being prepared.

The primary action is **Apply effect**. Applying commits exactly the candidate
being previewed, closes the browser and opens that effect's Creative tab when
available, otherwise its normal parameter tab. It creates one undo step.
**Cancel**, Escape and closing the browser discard the audition without changing
the piece, its snapshots, dirty state or history.

Retain the current keyboard contract: Enter in search or the results list must
not apply an effect. An explicitly focused Apply button may activate normally.
Use existing wheel-safe dropdowns and parameter formatting helpers.

### Inspect or replace an existing effect

An already authored effect continues to offer **Inspect effect** in Add effect.
This includes inherited, explicitly off and bypassed entries. Selecting it must
not replace its settings or silently resume it. Keep the preset chooser hidden
for these rows, as it is today.

In the inspector's Activation and preset area, replace the immediate preset
application button with **Preview preset…**. Open the same audition interface
locked to that effect; the primary action becomes **Replace with preset**.
Clearly state that replacement uses fixed preset values in the displayed scope.

Preserve replacement's existing bypass and inherited Creative behavior. A
bypassed effect stays bypassed during preview and after replacement. Explain
that fact and offer navigation to Resume; do not silently unbypass it to make
the preset appear stronger. Persistent Resume remains a separate explicit edit.

### Preview time and scope

- Capture the entry playhead, playback state, source-only preview state,
  comparison state, quality and scope. Pause normal playback while the browser
  owns transport. Browser controls must work while its parent window is modal.
- Start at the current absolute timeline frame. A and B use identical frame
  numbers, seed, source clock, canvas and preview dimensions.
- If a section is the edit target but the playhead is outside its occurrences,
  explain this and offer **Preview selected section**. Do not silently move the
  playhead or show an unrelated section as evidence of the candidate's result.
- That action chooses the nearest occurrence of the selected section and uses
  its actual absolute clock. Show the occurrence when a section repeats.
- The preview loop spans at most two seconds of the active playback scope;
  intersect it with the targeted section when editing locally. Reuse the
  existing scope/placement helpers for repeated and discontinuous ranges.
- Render at no more than 360 px on the longest edge, preserving canvas aspect
  and framing. Sample at up to 12 frames per second, using distinct valid frame
  indices on the original timeline. Do not change the document's FPS or feed a
  different time grid into the renderer. Label this as a sampled preview.
- A short composition or section uses its available frames. An intermittent
  effect may not fire in this window; explain that limitation. Do not reseed,
  accelerate or shift its phase to manufacture an example.
- On exit, restore the entry playhead and monitor preferences and leave normal
  playback paused. Apply returns to the committed working view. Cancel also
  restores a prior snapshot comparison if its document context is still valid.
  If the context changed, return to the current working piece, never an old one.

### Explain visibility

Show one compact primary status near the selected effect's title, with secondary
details available below it. Distinguish **In this scope** from **At this frame**.
Use renderer-backed facts and conditional guidance as different kinds of message.

| Evidence | Example wording | Action |
| --- | --- | --- |
| Effective bypass | Bypassed. Your settings are retained. | Open Resume control |
| Effective mode is off | Off in Section 02. | Open activation in that scope |
| Resolved module is disabled at this frame | Inactive at 00:03.20; active elsewhere in this scope. | Preview an active occurrence, only when one is known |
| Required source is absent | Granular halo needs Luminous forms in this section. | Open Object |
| A proven controlling value is zero | Bloom strength is zero at this frame. | Open the relevant parameter |
| Media is unavailable | Source video is missing. | Open existing source/relink workflow |
| A treatment depends on brightness, without input measurements | This treatment needs bright source areas. Threshold controls which areas contribute. | Open its actual threshold control |
| Matching before/after preview samples show little change | Little visible difference in these preview frames. | Suggest relevant controls; do not assert a cause |

The last two rows are guidance, not proof that the effect is inactive. Never infer
insufficient input brightness from the final graded image, which downstream
treatments may have changed. Measuring exact stage-input luminance is deferred;
do not introduce a renderer instrumentation system to satisfy this milestone.

Provide structural explanations across compatible treatments. Start specialized
zero/dependency rules with Tape damage, Frame jitter, Ghosts, Granular halo,
Bloom, Edge phosphor and Scan drag, auditing each against its renderer. Test
multi-module cases before claiming all of an effect is inactive. For unverified
conditions use the effect description instead of a speculative diagnosis.

Navigation links open existing controls and the correct group without changing
values, enabling sources, adding modules or altering timing. A Seek action must
be explicit. If finding the next active moment would require scanning/rendering
the entire piece, omit the action and explain the known scope-level behavior.
Navigating out of an audition first discards that temporary preview. Only offer
a control link when it addresses a live, editable property of the working piece;
for settings that exist only in an unapplied preset, show guidance until Apply.

### Explain the current piece

Add **How this look is built** to the existing Effects overview. Keep it compact
and collapsible. Derive its contents from the current composition and selected
scope so it also works for personal studies, remixes and pieces made from scratch.
Do not require a built-in study ID or title to produce the breakdown.

List the source and relevant applied treatments using a short contribution
sentence plus their actual status. Example contributions are **Model silhouette
provides the head**, **Edge phosphor creates a colored contour**, **Scan drag
pulls highlights into streaks**, and **Signal background textures dark areas**.
Descriptions are capability explanations, not claims of measured contribution
strength. Mark bypassed, currently inactive and intermittent entries accurately.

Clicking a source opens Object or Source. Clicking a treatment opens its
inspector. **Compare without this effect** temporarily compares the working
piece against a copy with only that treatment bypassed in the selected scope.
Use the same preview session and Before/Preview transport, with a Close action
and no Apply action. This comparison creates no undo entry. Existing persistent
Bypass controls remain separate and continue to create ordinary edits.

Do not offer temporary source removal as if it were an image treatment. Preserve
shared timing and source clocks when bypassing a treatment. For compound effects,
use their existing bypass semantics rather than toggling one guessed module.
Whole-clip comparisons also respect explicit section overrides; explain when a
section's local Resume keeps a treatment enabled instead of silently clearing it.
If Finishing, Master or authored transitions contribute, show a concise note and
link to the existing panel when available; do not invent fake effect entries or
promise that the breakdown is a layer stack.

## Implementation design

### Pure candidate construction

Introduce a small helper for creating an effect candidate from a complete
composition, stable section ID or whole-clip scope, effect ID, operation and
preset choice. Suggested home: `synth_effect_discovery.py`. It must:

1. Validate the effect, preset, operation, source compatibility and live target.
2. Deep-copy the composition, preserving the snapshot library and all unrelated
   values. Do not use a snapshot-free rendering copy as the committed document.
3. Resolve presets through `effect_preset()` and share existing add/replace
   semantics. Extract duplicated entry construction where needed; do not keep
   a preview implementation and an independently evolving Apply implementation.
4. Preserve bypass inheritance and section Creative neutralization. Preserve
   whole-clip versus section precedence. Never flatten authored states to the
   current frame or clear other section overrides to make a preview obvious.
5. Normalize and compile the candidate. Verify unchanged canvas, FPS, duration,
   time maps, source identity and snapshot library. A4 candidates may only edit
   the intended effect entry. Validate before any committed operation.

Freeze the target section by ID, not its row index. Capture a document identity
and revision/fingerprint; revalidate both before Apply. If edits, undo, source
relinking or an asynchronous result changed the base, cancel the stale candidate
with a clear message and offer a fresh preview. Never apply it to a replacement
document or overwrite intervening edits.

### One temporary preview owner

Extend or narrowly extract A3's routing into a session with an explicit purpose:
snapshot comparison, creative variation, effect preset, or contribution bypass.
Keep the existing working sequence as the sole committed/export source. Avoid
parallel ad hoc comparison dictionaries with inconsistent cleanup.

Discovery candidates must not participate in `audition_pending()` as unsaved
Creative variations. A3 Keep/Discard behavior must remain unchanged. Opening
discovery may suspend a read-only snapshot comparison; it must not abandon an
unresolved Creative variation. Use the existing Keep/Discard flow before entering
another session if that state is encountered.

Use a temporary quality override for discovery, independent of saved monitor
preferences. Adapt A/B labels to Before/Preview without changing snapshot labels.
Generalize the current comparison tooltip where it assumes B is always an
exportable working version.

No browsing action flushes unrelated pending text or parameter drafts into the
document. Normal field commits caused by explicitly leaving an edited field keep
their existing semantics. If unresolved drafts prevent a reliable baseline,
explain that they must be resolved in the editor before auditioning.

### Lifecycle rules

| Event | Required result |
| --- | --- |
| Effect/preset selection changes | Cancel obsolete work, rebuild from the captured base, and invalidate the old candidate display. Do not accumulate presets. |
| Apply | Revalidate the target and revision; commit exactly the accepted candidate once through composer/history; exit temporary mode. |
| Cancel, Escape, browser close | Discard candidate; restore valid prior viewer context; no document, dirty-state or history change. |
| Save, Save As, Save as study, Export while browsing | Window modality disables parent editing actions. If a menu/shortcut still reaches a handler, close/discard discovery first and operate on the working document through its normal validation. Never save/export a temporary candidate or implicitly Apply. |
| App close or document replacement | Cancel discovery, then run the existing working-document unsaved guard. No extra Keep/Discard prompt caused merely by browsing. |
| Unexpected context or media change | Reject old results and Apply; restore the current working context, not the captured old composition. |
| Rendering failure | Inline error with Retry/Cancel; no replacement of the working render or document. Apply stays unavailable until the candidate is validated and its current first-frame preview succeeds. |
| Existing export is running | Do not start discovery rendering. Explain that previews become available after export. |

### Scheduling and cache limits

Reuse `ComparisonFrames` and the existing rendering path. Retain a single 192 MiB
budget for Studio preview frame packets, including before/candidate banks and
queued deliveries. Do not allocate that budget again per effect or per preset.
Video decode/proxy and existing study thumbnail caches have separate bounds;
measure total memory rather than claiming 192 MiB is the whole process limit.

- At most one discovery frame/batch job runs and one latest request waits.
  Cancel at frame boundaries. Do not queue a job for every list selection.
- Foreground seeks and edits take priority. Stop discovery preparation on close,
  context changes or export, and coordinate with existing warming and study
  thumbnail work so hidden browsers do not compete for rendering resources.
- Before/Preview banks use identical absolute sample times. Cache keys include
  document revision, candidate content, render version, dimensions, time,
  source/proxy fingerprints and rendering context. A selection token alone is
  insufficient evidence that an image is valid.
- Cache only a small recently used set within the common byte budget. Reopening
  a selection may reuse proven-valid samples. Initial delivery may invalidate
  conservatively; never reuse a stale candidate to improve a hit rate.
- Reserve memory before producing packets; release cancelled reservations and
  pending deliveries. Reject late success and late failure callbacks by owner,
  document, generation and request identity.
- Keep expensive rendering and video decoding off the GUI thread. Each worker
  must own or exclusively use its video provider; do not seek a shared provider
  concurrently. Construct GUI pixmaps only on the GUI thread.
- Subject cutout or another prerequisite that prepares masks/assets must require
  an explicit **Prepare preview** action when those resources are not ready.
  Browsing must not silently start long preprocessing. Reuse existing local
  preparation, cancellation and error flows; do not add new dependencies.

### Frame facts and presentation metadata

Add a presentation-only explanation API, suggested home
`synth_effect_diagnostics.py`. Return structured codes, scope, evidence type,
plain-language messages and validated navigation targets. UI widgets must not
contain their own rendering/activation logic.

For exact frame facts, narrowly extract the existing cue/base-state resolution
from `render_sequence_frame()` into a shared helper if necessary. Preserve
operation order, numeric arithmetic and transition behavior exactly. Return the
same resolved settings and mapped clocks that rendering uses. Do not approximate
the current frame by selecting the nearest source recipe state.

Keep aggregate scope summaries from `describe_effects()` separate from these
frame facts. Avoid recompiling the full arrangement at every playhead tick:
reuse the current compiled sequence and throttle explanatory text updates. For
dynamic behaviors not exposed by that resolution, report the known configuration
or a conditional hint rather than pretending to have sampled the renderer.

Extend `synth_effect_catalog.py` or a sibling presentation module with short
contribution descriptions, verified prerequisite hints and control links. Use
stable effect IDs and parameter paths; validate links against the registered
effects/controls. Keep this metadata outside frozen recipes and saved studies.

## Work packages and commit boundaries

Complete these in dependency order. Use one coherent commit per package,
splitting a package only when its changes are independently reviewable.

### Package 1 Candidate semantics

- Add the pure candidate builder for Add, Replace and Compare without.
- Extract shared preset-entry construction from existing handlers as necessary.
- Verify inheritance, Creative neutrality, bypass, immutable originals, snapshot
  preservation, stable section targeting and unchanged clocks.
- Gate: candidate rendering equals rendering after its exact committed edit.

Suggested commit: `Share scoped effect candidates between preview and apply`.

### Package 2 Temporary preview sessions

- Give A3/discovery explicit ownership and lifecycle rules without changing A3
  user behavior. Add temporary quality and sample-window handling.
- Connect cancellation, generation rejection, media validity and common memory
  accounting. Preserve working-document Save/Export routing.
- Gate: cancel/failure/context replacement leaves no dirty state or stale image;
  existing A3 comparison and Keep/Discard tests still pass.

Suggested commit: `Add bounded temporary effect preview sessions`.

### Package 3 Browser and preset UX

- Add selected-candidate previews, Before/Preview, sampled playback and explicit
  Apply/Cancel to the compact browser.
- Route inspector preset replacement through the same preview flow. Keep applied
  rows' Inspect behavior and source compatibility filtering.
- Handle missing prerequisites, selected-section positioning and keyboard access.
- Gate: complete the shape and imported-video audition journeys through the UI
  with one Apply undo step and no edit on Cancel.

Suggested commit: `Preview effect presets before applying them`.

### Package 4 Visibility explanations

- Add shared current-frame resolution only as needed and protect pixel parity.
- Implement structured generic facts, verified specialized rules and conditional
  hints. Add navigation to the correct scope/control with no implicit edits.
- Gate: explanations agree with actual activation at cuts, morphs and repeated
  or retimed occurrences; unknown causes remain explicitly unclassified.

Suggested commit: `Explain effect activation and visibility in context`.

### Package 5 Composition breakdown

- Add How this look is built in the existing overview, using actual compiled
  sources/effects and concise contribution descriptions.
- Add inspector navigation and temporary Compare without this effect.
- Gate: the breakdown remains accurate after remix, edits, bypass and scope
  changes; temporary comparisons preserve all original settings and clocks.

Suggested commit: `Explain the treatments that build the current piece`.

### Package 6 Integrated validation and documentation

- Complete the native UI, lifecycle, performance and preservation checks below.
- Update README usage, the roadmap's A4 delivery status and CHANGELOG Unreleased
  with delivered behavior and actual limitations. Leave A5 and audio unchecked.
- Push the feature branch and create/attach a draft PR with exact check results,
  representative UI captures and any deviations from this plan.
- Keep version 0.3.0. Do not merge, tag, install or restart the user's app as part
  of this implementation handoff.

Suggested commit: `Document visual effect discovery and its validation`.

## Validation

### Behavioral tests

Extend neighboring tests and add focused discovery/diagnostics modules. Assert
observable document and image behavior rather than private widget layouts.

1. Search, filtering, selecting presets, Before/Preview, playback and Cancel
   leave normalized document, snapshot library, history and clean state intact.
2. Add and Replace preview pixels equal fresh renders after Apply at the same
   frame/quality. Undo recovers the original and Redo recovers the candidate.
3. Cover whole-clip and local scope, inherited bypass, inherited Creative values,
   authored off entries, section overrides and unrelated animated parameters.
4. Cover repeated sections, noncontiguous selected playback, resized effects-only
   and source-retimed sections, current frame outside the target, and transitions
   that consume both previous and current states.
5. Preserve imported-video framing, masks, source clocks and existing exported
   audio behavior. Cancel or replacing a preset must not modify source files.
6. A/B uses the same absolute timestamps and dimensions; A4 never reseeds noise,
   changes Timeline FPS or writes its quality override into preferences.
7. Cover rapidly changing selection, cancelling at each stage, failed decoding,
   missing/replaced media, a stale failure after a newer success, document
   replacement, Undo during an async job, export priority and window closure.
8. Prove bounded frame bytes plus reservations and pending packets. Test small
   artificial budgets, candidate eviction and cleanup of cancelled work.
9. Preserve A3 snapshots and variations, including restoration after cancelled
   discovery, unresolved variations, source-only preview, Save/Open and export.
10. Diagnostics cover confirmed off/bypassed/missing-source/zero cases, actual
    transition resolution, compound effects and conditional brightness hints.
    Never report configured-but-subtle as certainly inactive.
11. Contribution lists follow personal compositions and selected scope, including
    an effect bypassed locally but enabled elsewhere. Control navigation and
    temporary removal create no edits; persistent Bypass still does.
12. Keyboard tests cover Escape, focus order, Enter in search/results, explicit
    Apply, wheel-safe dropdowns and meaningful accessible names.

Use existing gates selectively during development. At integration, run the new
tests and these existing suites once, repeating only after relevant fixes:

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q \
  tests/test_synth_effect_browser.py \
  tests/test_effects_editor_core.py \
  tests/test_synth_effects_editor_integration.py \
  tests/test_synth_creative.py tests/test_synth_creative_ui.py \
  tests/test_synth_exploration.py tests/test_synth_exploration_ui.py \
  tests/test_synth_preview_scope.py tests/test_synth_preview_reuse.py \
  tests/test_synth_preview_ux.py tests/test_synth_bypass_timing.py \
  tests/test_synth_unsaved.py
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_synth_baseline.py
.venv/bin/python scripts/sync_version.py --check
git diff --check
```

The baseline suite currently has 12 cases covering frozen study pixels and model
identity. Do not regenerate its manifests to make a renderer refactor pass.
Add targeted sequence-resolution parity tests if extracting frame evaluation;
the existing fixed samples alone do not cover every transition boundary.

### Native review and performance

Review the development app at 1280×720, 1280×800, a roughly 380 px inspector and
a larger Mac window. Check square, original and Stories canvases. Capture the
browser preview, a visibility explanation and the composition breakdown. Ensure
the monitor remains visible and the bottom actions remain reachable by keyboard
and without horizontal scrolling.

Use New piece Shape and Text, Refined signal, Profile / Doryphoros, Mixed media /
two bursts and an available local imported-video composition. Avoid absolute
personal media paths in tests. Provide a small generated video fixture where
the test needs portable footage.

Measure before/after on the same local material: cold and cached first-preview
latency, selection-to-current-result latency, Cancel/seek responsiveness, actual
sampled playback, render job count and peak memory during repeated browsing.
Test a slow video source and a full-resolution monitor setting as well as 360 px.
Report measurements rather than promising universal real-time playback. There
must be no idle rendering after browser closure, no job per unselected preset,
no unbounded growth with continued browsing and no duplicate full arrangement
compile for each status-label update.

Build with `scripts/build_macos.py` without `--install`, verify the bundle and
smoke-test the new UI from the build using disposable app state. Preserve the
running installed app and the user's documents/preferences. If isolated native
launch is unavailable, report that limit and keep the build uninstalled.

## Completion checklist

- [ ] Two presets can be previewed on the same material without committing either.
- [ ] Applying commits the exact candidate once; Cancel and temporary bypass leave no edits.
- [ ] Current-frame facts and scope summaries are accurate and distinct.
- [ ] Brightness advice is conditional unless directly established by evidence.
- [ ] A personal composition has a useful, navigable contribution breakdown.
- [ ] The monitor remains usable in a small window.
- [ ] Preview work is bounded, cancellable and subordinate to editing/export.
- [ ] A1–A3 behavior and frozen study pixels pass their regression checks.
- [ ] Documentation, measured limitations and a reviewable draft PR are delivered.

## Execution handoff

When the user authorizes implementation, give GPT 6.1 Sol this instruction:

> Implement A4 using `docs/visual-effect-discovery-plan.md` in
> `/Users/ixtlan/Documents/ChatGPT/nebula-pipeline`. Start by checking the current
> branch, working tree and applicable repository instructions. The planning
> branch is `codex/visual-effect-discovery`, based on released 0.3.0. Read the
> existing browser, composer, A3 preview lifecycle and nearby tests before editing.
> Execute packages 1–6 in order with atomic commits and targeted verification.
> Preserve current rendering, studies, clocks, scope inheritance and A3 behavior.
> Keep auditions temporary, explanations evidence-based, and the monitor visible.
> Use normal code and renderers for all UI previews. Finish with a pushed draft PR,
> test results, native UI evidence and measured limitations. Do not start A5/audio,
> merge, bump the release, or install the app during this task.
