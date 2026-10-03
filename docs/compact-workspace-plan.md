# Compact Studio workspace

Prepared: 2026-10-03. Baseline: v0.4.2 / aad682b on main.
Status: implemented; see [delivery notes](compact-workspace-delivery.md) for
measurements, validation and compatibility details.

## Outcome

Give the artwork more room and make document, canvas, playback and editing
controls easy to distinguish. Keep the terminal palette, readable type and
existing editing capabilities. The user's screenshot shows four header rows,
a dedicated zoom row, two separated playback/cache lines, a 108 px section
lane around 68 px blocks, solid 9 px splitters and several footer rows.

This is a presentation and interaction milestone. Rendering, study defaults,
parameters, output frame rate, durations, source clocks, save format and export
quality must remain unchanged by navigation or workspace resizing. Preserve
Undo/Redo, unsaved-work guards, effect audition, snapshots, section selection,
proportional resize, loops and reorder. No hidden More/Fewer switch.

## 1. Document and canvas header — root

- Use two compact rows at normal desktop widths. Row one identifies the piece
  and groups New, Import, Open, Save, variations, Undo/Redo and Export. Put Save
  As and Save as study in the Save menu; keep keyboard/menu access and existing
  unsaved-document validation. Keep disabled actions synchronized.
- Row two groups the Study picker and Load/Browse with Canvas, Fit subject and
  a clearly labelled Timeline FPS control. Keep study selection deliberate:
  choosing an item must not silently replace the current document.
- Keep the current Study picker bounded, but allow its width to shrink. For
  narrow windows, wrap complete logical groups instead of clipping or shrinking
  text. Keep Canvas and FPS labelled and discoverable.
- Relocate contextual Restore from the global header into the inspector where
  its target is visible. Full screen becomes a compact view action.
- Export stays accessible regardless of inspector navigation or footer scroll.
  Its existing last-folder, asynchronous progress, cancellation and A/B working
  document behavior remain intact.
- Sequence/preset and detailed-copy windows retain their original controls and
  correctly show which FPS control applies; do not falsely expose composition
  history or silently unify source cadence with output FPS.

## 2. Monitor, transport and prepared-frame display — root

- Place compact zoom, Fit, 100%, snapshots/source comparison and full screen
  actions in a monitor toolbar. Use a responsive second line only when the
  available monitor width requires it. Keep Fit as a persistent automatic mode;
  preserve intentional numeric zoom. Avoid resetting the user's chosen zoom.
- Combine the scrubber and its prepared-range strip into one tightly aligned
  transport unit. The prepared line sits immediately below the track, not in a
  separate widely spaced row. Use a consistent magenta playhead and muted green
  prepared ranges. Preserve exact frame mapping, keyboard stepping and scrubbing.
- Add a concise prepared-frame count with a clear label, and keep measured
  preview FPS distinct from target FPS during playback. Report partial readiness
  honestly: cached frames can be a noncontiguous subset, not a full-playback
  guarantee. Keep full diagnostics in tooltips, accessible descriptions and
  actual error messages; no status text should pretend frames were rendered.
- Shorten routine status prose. The 192 MiB budget remains unchanged and is
  explained on demand rather than occupying a permanent sentence.

## 3. Compact section lane — GPT 6.1 Sol

- Draw roughly 46 px section blocks with two lines: number/name, then duration
  and repeat count. Reserve about 62–68 px including playhead and scroll space,
  replacing the current 108 px lane. Root adjusts the enclosing scroll host.
- Derive painting and hit areas from shared dimensions. Retain comfortable
  horizontal resize targets, group stretch, drag threshold, insertion markers,
  selection, loop context menus, repeated occurrences, Escape cancellation and
  edge autoscroll. Do not change proportional duration calculations.
- Give narrow sections useful elision/tooltips without pushing metadata outside
  their bounds. Keep the full section identity accessible.
- Distinguish the active editing section from arrangement/playback selection.
  Expose set_editing_section(section_id_or_none): whole-clip editing uses no
  single-section edit fill, while selected sections retain visible outlines for
  resize/reorder. Root synchronizes this with Composer scope.
- Move the long gesture sentence into an explicit timeline help control and
  tooltip. Keep imported-video resize mode directly reachable near the timeline.

## 4. Inspector and effects overview — root + GPT 6.1 Sol

- Root simplifies the Composer header and removes the redundant Parameters /
  Scope frame. Editing scope stays pinned above tabs with an explicit whole-clip
  or named-section label. Shared Master/Source/Timing scope remains explicit.
- Root relocates the existing contextual Restore action here and provides the
  FPS header binding. The current parameter editor, drafts and scope semantics
  remain intact. Arrange remains a separate bounded view with a return route.
- Sol compacts the effects overview: count/title and Add effect share a row;
  source summary and one Edit object action share a clear group. Keep direct
  inspection of each source in composite sources. Avoid duplicate large object
  action rows. How this look is built stays discoverable and expandable.
- Effect names remain primary; Bypass/Resume states and Remove stay visible,
  labelled and keyboard accessible. Remove remains visually secondary and
  undoable. Do not change activation, inheritance, presets or removal semantics.
- Reduce nested borders and dead spacing with targeted style properties, not
  a global reduction in every parameter field or dialog. Maintain the 380 px
  minimum inspector, preserve the user's saved divider position and use a
  viewport-favouring default for fresh workspaces.

## 5. Dividers and footer — root

- Replace broad solid splitter bars with a thin visible line/grip while keeping
  an 8–10 px mouse hit area. Provide breathing room so the divider cannot be
  mistaken for prepared-range or export progress. Preserve vertical and
  horizontal resizing, saved workspace state and noncollapsible panels.
- Use one compact preview-settings row for Playback scope, preview quality,
  Auto prepare and Prepare. Allow logical wrapping at narrow widths. Place
  gesture help and video resize mode with the section lane.
- Remove redundant permanent document-status lines; show operation feedback in
  a compact status area. Export progress and Cancel appear only while needed;
  completion/error feedback remains available after the job finishes.

## Delegation and file ownership

All agents share the feature checkout. No agent switches branches, commits,
pushes, installs, controls the user's running app or edits renderer modules.

- Root: synth_studio.py, synth_exploration_studio.py, studio_theme.py, new
  workspace/transport widgets, Composer portions of synth_composer_ui.py after
  SectionTimeline, CachedRangeStrip, workspace integration tests and docs.
- Sol timeline: SectionTimeline class only in synth_composer_ui.py, new compact
  timeline tests, and existing timeline gesture tests only when coordinates
  need adapting. Do not edit CompositionPanel or CachedRangeStrip.
- Sol effects: synth_effects_ui.py and focused effects overview tests. Use
  dynamic property `secondaryAction` on quiet actions and `compact` on small
  chrome; root provides shared theme selectors. Do not edit the composer or
  shared theme. Retain public control attributes used by existing integrations.

## Verification and acceptance

1. Record baseline widget measurements at 1280×800, 1440×900 and a wide desktop
   size; compare against the same composition and splitter settings. Target
   roughly 100–150 logical pixels reclaimed for the monitor where possible;
   report measured results rather than guaranteeing that estimate everywhere.
2. Check 1280×720 minimum workspace, 380 px inspector, wide/maximized window,
   9:16 and landscape canvas, ordinary effects overview and a long parameter
   editor. No clipped primary actions or unexpected horizontal panel scrolling.
3. Exercise actual Qt selection, single/group resize, reorder, loops, Escape,
   keyboard shortcuts and wheel protection. Do not rewrite renderer baselines.
4. Verify whole-clip and section scope, source replacement, shared timing,
   pending text, contextual Restore, Add/Remove/Bypass, auditions and snapshots.
5. Verify prepare/cancel, partial cache, playback/stepping, A/B, video Before,
   export progress/cancel/success and remembered MP4 destination. Navigation and
   resizing must leave composition content, history and render settings intact.
6. Run focused suites plus relevant existing integrations once; expand only for
   changed behavior or unresolved failures. Inspect native macOS layout and
   interactions on a disposable review composition before installation.

## Delivery

Commit the plan, then atomic implementation packages and delivery notes. Use a
reviewable PR against main. The user has standing authorization to merge and
install without further confirmation. After checks pass, release the next
compatible patch version, merge, build from main, verify the app signature,
preserve any current unsaved composition, quit normally, install and reopen it.
Never discard the user's changes or force-quit an active export.
