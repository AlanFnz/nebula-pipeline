# Compact workspace delivery

2026-10-03 · v0.4.3

Implementation follows [the recorded plan](compact-workspace-plan.md). Two
GPT 6.1 Sol agents implemented the bounded timeline and effects overview work;
the root agent integrated the header, inspector, transport, dividers and footer.

## Changes

- Document actions occupy the first header row; Studies, Canvas and the actual
  global Timeline FPS control occupy the second. Logical groups wrap when space
  is limited. Export remains visible at the top. Save is a split button: main
  area saves; the arrow exposes Save As and Save as study.
- Zoom, Fit, snapshots/source comparison and full screen share the monitor bar.
  Numeric zoom remains intentional; Fit remains automatic. The prepared-range
  strip sits directly under the scrubber, with a separate actual prepared count
  for the active playback scope. Playback still reports measured versus target
  FPS. Long diagnostics remain in tooltips; error status remains readable.
- Timeline blocks are 46 px tall, in a 62 px drawing surface / 78 px scroll host.
  Names and duration/loops use two clipped, elided lines, with full identities in
  tooltips/accessibility. Local editing uses a fill; selection uses an outline.
  Shared whole-clip panels clear the local editing fill without losing selection.
- Inspector framing is simpler. Restore follows the current panel and scope.
  Add effect and Edit object sit alongside their headers; Bypass/Resume and
  Remove remain direct, labelled actions. No effect semantics changed.
- Dividers use a thin line and grip inside the existing 9 px drag area. Preview
  options share a wrapping row. Export reveals progress/Cancel and scrolls them
  into view; completion and failures remain in operation status afterward.

## Measurements

Same shape composition, no saved divider override, offscreen Qt with the app
font/theme, compared with v0.4.2. Sizes are logical pixels. Existing saved splits
and zoom are retained, so an individual workspace can have different gains.

| Window | Previous viewer | New viewer | Height gained |
| --- | --- | --- | --- |
| 1280 × 720 | 740 × 240 | 816 × 357 | 117 |
| 1280 × 800 | 740 × 309 | 816 × 437 | 128 |
| 1440 × 900 | 837 × 409 | 921 × 537 | 128 |
| 1728 × 1017 | 1011 × 526 | 1112 × 654 | 128 |

The workspace starts at y=75 instead of y=164 in this comparison. The inspector
still has a 380 px minimum. A narrow monitor wraps its controls rather than
clipping comparison actions. Full-frame preview performance and the 192 MiB
budget are unchanged; this release creates screen space, not faster rendering.

## Validation

- Native macOS inspection of a disposable Profile / phosphor scan copy at 9:16,
  including effect inspection and contextual Restore. Corrected Save-arrow
  spacing and widened the canvas picker after the visual check.
- Timeline agent: 67 tests across compact layout, resize, reorder, loops and
  reorder integration; drag/reorder screenshots inspected.
- Effects agent: 9 compact layout/action tests plus 40 editor, removal and
  integration tests; checked 380/490 px widths and long names.
- Root integration: 20 timeline/effects/workspace integration tests passed.
- Final workspace group: 32 tests passed across compact chrome, layout, zoom,
  preview behavior and video/study UI. Includes Save/rebuild lifecycle, actual
  FPS binding, selection versus editing, scoped prepared counts, comparison
  wrapping, Fit/numeric zoom, and visible export progress/cancellation.
- Preview scope: 14 tests passed after updating the partial-preparation wording.
- Frozen rendering: 12 tests passed, checking 121 existing scenarios and model
  asset identities. No fixture changes, renderer changes or document migrations.
- Version metadata, CLI version, Python compilation and diff whitespace checked.

Test groups overlap; the counts above are not a unique-test total. Local QA
captures/logs remain outside the repository in `/private/tmp/nebula-compact-qa`.
