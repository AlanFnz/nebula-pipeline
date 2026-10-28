# Preview performance audit

Prepared: 2026-10-28.
Baseline: Nebula 0.48.1, commit `0e7c21b7c865da76c578571faa0ece638ba3f75a`.
Status: scope and implementation inventory complete; measurements are next.

Reduce the wait between an edit and its visible result, and the time needed to
prepare playback, while preserving the current images and editing behavior.
The first milestone delivers a reproducible diagnosis and ranked optimization
plan. Renderer or scheduling changes follow as separate, measured patches.

## Scope and acceptance conditions

Cover the current SynthStudio path from control interaction to displayed frame,
including composition compilation, resource loading, rendering, caching and the
Qt event loop. Measure the installed macOS app as well as the development build.
Keep export as a correctness check for changes to shared rendering code.

- Preserve selected monitor resolution, especially Full canvas. Record any
  authored Low-res finish separately from monitor quality.
- Preserve raw RGB output for identical inputs on the same environment, including
  source/effect clocks, seeds, automation, intensity, effect order and blending.
- Preserve text, canvas, durations, audio synchronization, Undo/Redo and saved
  document compatibility. Use disposable copies of studies and user projects.
- Keep stale results out of the viewer and preserve A/B ownership. Faster work
  must still respond to cancellation and document changes correctly.
- Keep the existing frame-cache budget and account for worker reservations.
  Measure total process and child-process memory separately; faster rendering
  cannot depend on unbounded retained intermediates.
- No speed-up claim may come from omitted effects, lower pixel precision,
  reduced resolution, shorter measured workloads or altered temporal sampling.

## Representative workloads

Start with five workloads. Freeze the exact documents, source assets, fonts and
their hashes in a local measurement manifest before running the baseline.

| Workload | Material | Main coverage |
| --- | --- | --- |
| Current Guerrilla Radio composition | Saved soft-red version, 45 clips, 1080 by 1920, with its existing project effects and soundtrack | Primary editing case; many short shots, text, grain and stacked treatments |
| Text / one more try | Built-in `text-dye-transfer` study at its saved canvas | Text changes, rotated cuts, optical transitions and dense arrangement |
| Memory / afterimage garden | Built-in `image-memory` study | Time-dependent displacement, trails and signal texture |
| Color film / rotating die | Built-in `color-film-die` study | 3D source, shading, texture and compositing |
| Generated video fixture with treatments | A reproducible local 1080p clip, imported through the current video path | Decode/seeking, proxy reuse and effects over footage |

Use Full canvas first. Add paired 720 px measurements to identify resolution
scaling; compare before and after at the same resolution. Retain each study's
original FPS and canvas. Additional particle, imported-model or subject-cutout
cases enter the deep pass when a finding affects those paths.

The primary project is currently at
`output/guerrilla-radio-soft-red/Guerrilla-Radio-soft-red.nebula.json`.
Copy it and resolve its existing media references for the audit; keep generated
media and machine-specific manifests under ignored `output/preview-performance-audit/`.

## Measurement protocol

Record commit, build type, Python and dependency versions, macOS, chip, memory,
power mode, canvas, quality, effect settings and background workload. Run timing
trials serially on the same Mac. Avoid concurrent tests, exports, builds or a
second rendering app instance. Use isolated `NEBULA_STATE_DIR` settings for QA.

Define cache states explicitly: a fresh process, resources already loaded but
the requested frame uncached, and the same frame served from cache. Report
video-proxy creation separately from later decoding. Do not call a run
disk-cold merely because the Python process was restarted.

Begin with a short survey of all five workloads. Deep-profile the two largest
contributors to user-visible waiting. For repeated interactive scenarios,
collect at least 20 observations and report count, median and 95th percentile;
retain the raw samples. Report cold starts and expensive preparation runs with
their individual timings and counts rather than a percentile from a tiny set.
Run profiled and unprofiled trials separately to quantify instrumentation cost.

| Scenario | Measure | Required controls |
| --- | --- | --- |
| Open composition | Request to first correct visible frame; resource-load time | Fresh process versus already loaded resources |
| Single parameter edit | Last input event to the corresponding displayed frame | Local and project scope; early and late effects in the stack |
| Rapid slider drag | Final input to final correct frame; obsolete work duration | Fixed input sequence and timestamps; include time spent waiting on cancelled work |
| Scrub and revisit | Uncached seek latency, cached seek latency and hit rate | Fixed absolute frames, including cuts, transitions and backward seeks |
| Add project effect | Open/select to current candidate frame; Before/Preview switch | Same resolution, playhead, preset and document |
| Prepare playback | Time to prepare a fixed list of absolute frames; frames per second | Record requested and completed frames, auto versus explicit preparation and cache bounds |
| Continued editing | UI event-loop delays, peak memory and retained memory | A fixed ten-minute edit/scrub/compare sequence; inspect growth after settling |

Time the entire interaction, including debounce, queue wait, synchronous UI
work, worker execution and presentation. The existing worker render duration
alone does not represent what the user waits for. A GUI receipt timestamp is a
useful boundary; validate painting/presentation behavior in the native app.

## Existing implementation and investigation targets

These are code observations and profiling targets, not measured bottlenecks.

| Area | Current implementation | Question for the audit |
| --- | --- | --- |
| Jobs and scheduling | `synth_studio.py` has foreground RenderJob, batched PreparePreviewJob, debounce, generation guards and cancellation | How much latency occurs before work starts, and how quickly does obsolete work release the foreground path? |
| Frame reuse | `synth_preview.py` retains proven unaffected frames and schedules bounded windows; `synth_comparison_preview.py` shares a 192 MiB budget across banks | Which edits cause avoidable misses, and how much reuse is already effective? |
| Effect discovery | `synth_effect_preview.py` preserves chosen quality and bounds both comparison sides | How costly are selection changes and repeated comparisons at full resolution? |
| Document preparation | Jobs deep-copy settings and sequences; `synth_sequence.py` normalizes a sequence when rendering a frame | How much time and allocation does this consume for a many-shot composition? |
| Source and effect rendering | `synth.py` dispatches renderers; sequence rendering includes raster conversions, transitions and master controls | Which stages dominate, and are immutable geometry, text masks or intermediate images recomputed? |
| Video and media | `synth_video.py` owns source/proxy frames and cancellation; prepared batches own their providers | Are decoding, provider lifetime or repeated resource initialization significant? |
| UI work | Compilation, inspector refresh, explanations, waveform/thumbnail work and viewer updates share the interaction path | Does synchronous work delay input or delivery even when rendering is quick? |

`tests/measure_preview.py` measures the earlier Print / Scan editor, so it is
not the baseline harness for this milestone. The historical timings in
`visual-effect-discovery-delivery.md` predate Full canvas auditions. Reuse
the patterns and correctness checks, while measuring the current SynthStudio.

Existing safeguards include `test_synth_preview_reuse.py`,
`test_synth_preview_scope.py`, `test_synth_preview_ux.py`,
`test_synth_effect_discovery_ui.py` and `test_synth_exploration_ui.py`.

## Execution and deliverables

### 1 Baseline and repeatable scenarios

Add a development-only measurement harness around the current app and renderer.
Freeze the local workload manifest, event sequences, frame lists and RGB hashes.
Capture the first survey and reproducibility checks before changing app behavior.

Deliver the runner, local raw measurements and a baseline table. Completion
means another run can repeat the same operations with the same final pixels and
clearly identified cache conditions.

### 2 Cost attribution and diagnosis

Profile the selected expensive scenarios at the document, UI, resource, render
stage and presentation boundaries. Include native-library and child-process
work when a Python profile cannot explain the elapsed time. Track allocation
and copying only where needed to explain measured cost. Separate overlapping
worker activity from the wall-clock path the user experiences; avoid adding
nested or concurrent timings as if they were independent.

Deliver a ranked list of up to five opportunities. For each, record reproduction,
evidence, affected workloads, time share, plausible upper bound on total benefit,
implementation effort, correctness risk and a focused verification method.
Mark uncertain causes as hypotheses. A slow stage's removal is an upper bound,
not a promised speed-up.

### 3 Separate optimization patches

Choose the first patch from the measured ranking. Candidate areas include reuse,
normalization and copying, cancellation granularity, redundant UI work and
resource lifetime. Intermediate caching must model every dependency, including
time, random seed, masks, stage input, upstream settings and external assets.
Select concurrency or GPU work only if the evidence supports its cost and scope.

Each patch owns one problem and includes paired measurements and relevant
regression checks. Keep the audit evidence distinct from production changes.

### 4 Validation and delivery

Repeat the same workloads, frame lists and cache states on the same machine.
Compare raw pixels against the frozen baseline, with special coverage for
nonsequential requests, cue boundaries, feedback, source changes, A/B and audio
reactivity. Verify affected export frames through the shared rendering path.
Existing frozen-study compatibility checks remain authoritative.

Accept a patch when its gain exceeds observed run-to-run variation, the target
interaction improves, other representative cases show no unexplained material
regression, and the image, behavior and memory conditions above hold. Establish
numeric latency targets after the baseline. Report absolute milliseconds and
seconds alongside percentages. A final native-app check precedes installation.

## Milestone tracking

- [x] Define scope, representative workloads and correctness conditions.
- [x] Locate the current render, scheduling, cache and measurement paths.
- [ ] Freeze fixtures and add a current-app measurement harness.
- [ ] Capture the baseline and select scenarios for deeper profiling.
- [ ] Deliver the ranked diagnosis and first patch recommendation.
- [ ] Implement and validate individually justified optimization patches.
- [ ] Record final results and install the verified app update.
