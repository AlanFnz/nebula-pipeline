# History and plans

[Documentation](README.md) · [Current status map](creative-controls-audio-roadmap.md) · [Changelog](../CHANGELOG.md)

This inventory separates past design/validation from current usage. Dates and
results below belong to their recorded work. A completed bounded milestone does
not imply that every later idea in its plan shipped. Original checklists and
handoff instructions are preserved as history, not new instructions to execute.

## Interface and editing records

| Record | Recorded scope/status | Current guide |
| --- | --- | --- |
| [Editing and preview plan](editing-preview-plan.md) | 2026-09-30 milestone delivered; later roadmap preserved. | [Editing](editing.md) |
| [Study browser plan](study-browser-plan.md) | 2026-09-30 library milestone delivered. | [Study management](editing.md#save-and-manage-studies) |
| [Effects editor UX](effects-editor-ux-plan.md) | 0.2.0 focused inspector delivered. | [Effects](editing.md#effects-and-animation) |
| [Compact workspace plan](compact-workspace-plan.md) / [delivery](compact-workspace-delivery.md) | 0.4.3/0.4.4 layout and measurements. | [Monitor](monitor-and-export.md) |
| [Studio design plan](studio-design-plan.md) / [delivery](studio-design-delivery.md) | 0.9.0 charcoal/native-type direction delivered. | [Editing](editing.md), [inspector](object-inspector.md) |
| [Visual discovery plan](visual-effect-discovery-plan.md) / [delivery](visual-effect-discovery-delivery.md) | 0.4.0 auditions and explanations delivered. Captures show that UI. | [Effects reference](effects-reference.md) |
| [Timed automation plan](timed-effect-automation-plan.md) / [delivery](timed-effect-automation-delivery.md) | 0.5.0 bounded gestures, with 0.5.1–0.5.3 follow-ups. | [Timed gestures](editing.md#timed-gestures) |
| [Reusable effects plan](reusable-effects-plan.md) | First region/compatibility milestone delivered; later extraction remains partial. Ordering shipped after this plan. | [Order and instances](editing.md#processing-order-and-instances) |

## Creative and audio records

| Record | Recorded scope/status | Current guide |
| --- | --- | --- |
| [Original creative/audio roadmap](archive/creative-controls-audio-roadmap-2026-11-06.md) | Accumulated proposals through 2026-11-06, superseded by the current status map. | [Status](creative-controls-audio-roadmap.md) |
| [Imported soundtrack plan](imported-soundtrack-plan.md) | B1 delivered in 0.10.0; band-energy mapping followed later. | [Sound](sound.md) |
| [Radial/audio study plan](radial-audio-study-plan.md) | 0.11.0–0.11.2 study and continuous response slice; local demos need audio. | [Sound](sound.md#import-a-soundtrack-and-make-visuals-react) |
| [Image memory plan](image-memory-plan.md) | Generated-form memory delivered 2026-10-17; arbitrary frame history excluded. | [Memory](sources-and-studies.md#memory--afterimage-garden) |
| [Tension plan](tension-study-plan.md) | Visual treatment and study revisions delivered through 2026-10-26; sound adapter pending. | [Tension](sources-and-studies.md#tension--elastic-signal) |
| [Burning print plan](text-film-burn-plan.md) | 0.28.0 print treatment/study delivered. | [Text studies](sources-and-studies.md#text--burning-print) |
| [Visual sound implementation](visual-sound-prototype.md) | Versioned DSP, old UI behavior, personal variants and historical MIDI hardware observations. | [Sound](sound.md), [MIDI](../LIVE_MIDI.md) |

## Performance evidence

[Audit plan](preview-performance-audit.md) and
[results](preview-performance-audit-results.md) record the 2026-10-28 source-build
baseline at 0.48.1. The results remain in their original Spanish. They identify
measurement boundaries and incomplete installed-app validation. They do not
measure 0.84.0 or prove that the complete optimization proposal was delivered.
The [runner reference](preview-performance-audit-runner.md) explains its local
fixture dependencies and visible-window behavior.

The [Print / Scan editor record](legacy-clip-editor.md#historical-validation-and-measurements)
also retains the older README's local preview measurements with their missing
build/date provenance explicit.

## Inventory boundaries

The maintained corpus includes root documentation, `docs/`, asset READMEs and
the Ableton integration. Third-party font/license texts are retained unchanged.
`build/`, `dist/`, environments, caches, generated media and external UX reports
are excluded. Asset provenance belongs in the font/model/icon READMEs; it is not
evidence of current UI behavior.
