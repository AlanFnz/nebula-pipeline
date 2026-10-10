# Studio interface delivery

2026-10-10 · v0.9.0

Implementation follows [the development plan](studio-design-plan.md). Three
GPT-6.1 Sol agents handled the shared theme, parameter controls and effect
inspector. The root agent reviewed their changes, integrated workspace controls
and verified the combined interface.

## Delivered

- Neutral charcoal surfaces, off-white labels, native sans-serif typography and
  monospace numeric fields. Green identifies actions and selection; amber
  identifies automation curves. Menus, dialogs, Studies and effect discovery
  use the same visual system. Keyboard focus and disabled states remain clear.
- Responsive parameter rows: labels, sliders, fields and reset share a row when
  space permits and wrap in narrow inspectors. Choice fields show full labels;
  text and artwork editors keep their useful size. Ordinary project provenance
  no longer repeats under every control. Animated, inherited, local and
  unavailable states remain explicit, with accessible explanations and tooltips.
- Direct effect Restore, Bypass/Resume, Remove and supported Add instance
  actions. Logical control groups open individually; the first starts open.
  Manual expansion is remembered during the panel session. Search, explicit
  group filters and diagnostic links reveal their matching controls.
- Arrange clips and Automations sit beside the timeline. Preview quality is
  beside playback, and the subordinate prepared-frame strip explains its role.
  Editing scope remains prominent and independent of timeline selection.

## Review and validation

- Inspected offscreen layouts at 1280×720, 1440×900 and 1728×1017, including a
  380 px inspector, Studies, effect discovery and automation. Visual review
  caught and corrected wrapped-row overlap when narrowing an existing panel;
  the responsive layout now measures its wrapped height before placement.
- Frozen rendering checks: 12 tests passed, covering 121 stored scenarios and
  bundled model identities. No baseline files or rendering code changed.
- Workspace/layout: 13 tests passed. A later navigation, repetition and compact
  workspace run passed all 45 tests after adapting two legacy visibility
  assertions to navigate through collapsed groups.
- Timeline resize, reorder, sticky scope and preview checks passed 56 tests;
  the remaining legacy visibility assertion was updated and passed in the
  45-test navigation run above.
- Theme/widget, Studies, discovery and automation checks: 69 tests passed.
  Checked secondary buttons were also inspected in actual Qt rendering.
- Inspector: 32 layout/compact/instance/diagnostic tests and 75 editor, scope
  and discovery tests passed, plus the Region edit/save/undo regression.
- Parameters: 45 tests passed, including narrowing and re-widening an integrated
  inspector without overlap, clipping or document changes. A separate 49-test
  automation/text/scope integration group passed. All 619 parameter paths were
  also exercised at three inspector widths. Numeric precision, release commits
  and fixed/animated conversions are retained.
- Version metadata, CLI version, Python compilation and diff whitespace checked.
- Built and installed the 0.9.0 macOS bundle and verified its local code signature.
  Reopened the user's saved Portrait / grain CRT document at 720×480, 15 FPS and
  65% viewer zoom. Checked the native inspector and search revealing a collapsed
  group. The saved document remained byte-identical after restart and navigation.

Groups overlap; these counts are not a unique-test total. Local screenshots and
logs are kept in the ignored `.validation/ui-review/` directory.

## Scope and limits

This release changes presentation and navigation. It does not change rendering,
Study settings, saved document formats, source handling or timeline semantics.
Preview performance and cache budgets are unchanged. Saved splitters and viewer
zoom take precedence over the default layout. The Study picker and existing
effect parameter units remain compatible with current workflows. Group expansion
is session navigation state, not saved composition data.
