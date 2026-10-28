# SynthStudio performance runner

Run from the repository with its existing `.venv`. This is an opt-in measurement
tool; importing or launching the normal app does not enable instrumentation.
No production renderer, quality setting, cache budget or scheduling rule is patched.
The runner drives disposable documents through the real SynthStudio callbacks.
A small coroutine driver returns to the outer Qt event loop between actions; it
uses neither QTest polling waits nor nested event loops for presentation.
It uses a native Cocoa Qt window with the test-only always-on-top flag to keep
the monitor exposed, not the offscreen Qt platform. User app windows are not
closed or restarted. The flag is never applied by normal app launches.

```sh
.venv/bin/python tools/audit_synth_preview.py --freeze
.venv/bin/python tools/audit_synth_preview.py --case guerrilla --samples 2 --survey --label survey-guerrilla-full
.venv/bin/python tools/audit_synth_preview.py --case text-dye-transfer --samples 20 --no-prepare --label baseline-text-full
.venv/bin/python tools/audit_synth_preview.py --case guerrilla --samples 1 --profile --detail --no-prepare --label diagnostic-guerrilla
.venv/bin/python tools/audit_synth_preview.py --case guerrilla --session-only --session 600 --label session-guerrilla
```

Use unique labels. Run commands in series, with no builds, tests, exports or other
render benchmarks at the same time. Leave the user's existing app alone. Record
background activity; do not silently close other apps. `--freeze` generates the
1080p fixture with the installed FFmpeg and freezes local copies, absolute resource
paths, original document/audio hashes, bundled asset hashes, canvas, FPS, effects,
cut-adjacent frames and the fixed preparation list in `manifest.json`. The test process redirects the video proxy directory into its isolated state;
this is a storage-path override, with no decode/quality changes. The video
case subsequently imports through `start_video_import` / `ImportVideoJob`, records
proxy preparation separately, adds image treatments through the ordinary composer,
and adds its resulting document to the manifest. Do not freeze again mid-baseline.

All files go to ignored `output/preview-performance-audit/`. Every run gets an
isolated `NEBULA_STATE_DIR` beneath that directory. No existing settings or studies
are edited. The original project is only read. No installation is performed.

`events.jsonl` contains timestamped worker submission/start/end, cancellation requests, display receipt/return,
viewer paint completion, memory, cache accounting and 20 ms event-loop pulse
samples. `samples.json` contains individual interaction samples, including the
synchronous action duration, receipt latency and latency through paint completion.
Samples and references assert both the chosen quality index and dimensions
derived independently from the frozen case canvas, including effect auditions.
PNG references have separate SHA-256 values for raw RGB and the encoded PNG.
The latter is not a substitute for RGB identity.
Restoring frame zero asserts equality with that run's initial raw RGB hash.

The default launcher starts a fresh child process and timestamps it before
spawning. `fresh_process_open` includes Python/Qt imports, fixture loading,
construction, rendering and painting. `fresh_construct_open` separately measures
construction/showing after imports and JSON loading. Neither is Finder launch time. Subsequent
uncached samples clear only the rendered-frame cache: fonts, renderer caches,
video providers and the operating system disk cache can remain warm. A cached
sample follows the uncached request for the same absolute frame. A separate `scrub_navigation` sequence retains the normal cache and records
natural hits/revisits. Forced-miss trials clear the cache and restore its current
namespace. Frames span early and late positions, backward seeks and cut boundaries. `--quality 720` is only a
resolution-scaling control; it never replaces the Full canvas baseline. Each case
retains its own authored canvas, FPS, effects and explicit Low Res Finish.

Clip/project edits call the ordinary object/effect parameter callback, with
all normal compilation, history, invalidation and debounce work. They alternate
0.90/0.91 on text opacity (both text cases), Memory light, Solid light, or video
Bloom strength. The document is reset between clip and project scope, so a clip
override cannot mask the project edit. Samples retain final RGB hashes. The rapid committed
input scenario queues eight values at nominal 15 ms intervals and records their
actual dispatch times. These timings must not be described as a physical slider
drag: the existing slider has tracking disabled and commits on release.

The browser runs Add Project Effect, selects candidates, and alternates
Before/Preview through the real comparison owner and shared cache. Browser opening
includes selecting a specified candidate. Fixed-list preparation uses the existing
four-frame batching, providers and reservations in automatic/explicit modes. It
sets the fixed target directly, so it excludes the public scheduling timer. Separate
`public_preparation` events measure the normal automatic and explicit entry points,
including their actual, potentially different, frame lists. `--survey` omits these
longer public-window preparations; `--no-prepare` omits both preparation variants.

The ten-minute session enables normal automatic preparation and dispatches one
action every five seconds: seek, edit, undo, seek, open audition, Before, Preview,
close audition. It records action completion timestamps, event-loop gaps and final
settling. Completion timestamps include synchronous work and are not input-dispatch timestamps.
Audio is not played; existing scrub/audio synchronization callbacks still run.
Memory snapshots report own RSS and child RSS separately. RSS is not the bounded
RGB cache, is not physical footprint, and does not prove a leak. Transients shorter
than the one-second sampling interval may be missed. Cache samples include worker
reservations and assert the existing 192 MiB bound.

`--profile` uses one process collector across construction and outer-loop turns,
including deferred selection/compilation, delivery and workers. A calibration on
this Python 3.14.6 build showed that cProfile collects both the main and worker
threads, and rejects a second active collector. Do not interpret `process.prof`
as a per-thread profile. Use separate opening, render-only and interaction runs,
worker boundaries and UI spans for attribution; recheck thread coverage on a
different Python build. `--detail` adds nested method spans. Treat cumulative times as overlapping;
never sum nested calls into a wall-clock total. Profiled runs are diagnostic and
must be compared with unprofiled trials to assess observer overhead. The standard
run still has logging, pulse, memory and paint observers; its overhead needs its
own paired check.

The native viewer's `paintEvent` return confirms that Qt executed the draw. It does
not prove WindowServer composition, display scanout, or exact human-visible latency.
The saved native viewer image verifies content; installed-app observations must be
reported separately, with their coarser timing boundaries. Python process restart
does not imply a cold filesystem cache. Preserve failed/prototype runs, label them
as such, and exclude them from completed baseline aggregates.

Additional focused runs:

```sh
.venv/bin/python tools/audit_synth_preview.py --case guerrilla --drag-only --samples 20 --label physical-drag
.venv/bin/python tools/audit_synth_preview.py --case guerrilla --prepare-only --label preparation-window
.venv/bin/python tools/audit_synth_preview.py --case image-memory --scaling-only --quality 720 --frames 120,180 --samples 2 --label scaling-memory-720
.venv/bin/python tools/audit_synth_preview.py --case guerrilla --scaling-only --frames 0,1 --samples 20 --quiet-observers --label observer-control
.venv/bin/python tools/summarize_synth_audit.py
```

Physical dragging uses the existing Bloom strength control on Guerrilla Radio,
with eight QTest mouse moves and the release event on a visible control. It
asserts tracking=False and unchanged generation before release, and retains the
press/move timestamps as well as release-to-paint latency. On the other four cases,
`--drag-only` uses the same frozen parameter as the single-edit scenarios. The
target alternates between 18% and 15% of slider width; committed values are logged.
`--open-only` records one costly construction/open, reference and native viewer
image without running the interaction matrix. `--frames` selects an explicit
absolute-frame subset; it does not resample time. Labels must be unique: the
runner refuses to append to an existing event log.

The summarizer reports each run independently, labels profiler diagnostics
separately and excludes them from `valid_baseline`. Nearest-rank p95 is accompanied
by sample count and originals; do not cite it as a robust percentile for small
counts. `excluded-runs.json` records failed/prototype runs and why their timings
are invalid; `valid_baseline` excludes these even if a prototype completed.
The original development of this harness uncovered both GIL starvation from
QTest polling and Cocoa drawing deferral in nested event loops. Neither is an
application bottleneck. Only the final outer-event-loop runner is admissible.
Candidate completion also checks the audition owner/effect/side; receipt of an
intermediate working frame during the 300 ms selection debounce cannot complete
a candidate sample. These safeguards matter when repeating this audit.

A concurrent benchmark/build/test on the same Mac invalidates timing even when
it belongs to another chat. Preserve its observed overlap in `excluded-runs.json`,
wait for the independent workload to finish, and rerun with a new label. Do not
terminate the user's other tasks or apps. Background application activity and
power mode are part of the environment record; an account of that load is not
evidence that competing benchmarks were harmless.
