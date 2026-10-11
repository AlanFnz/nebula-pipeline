# Radial bloom and first audio-reactive Study

Recorded: 2026-10-11. Reference: local `ref-6.mp4`. Delivered in 0.11.0.

## Result

Build an editable short vertical Study matching the reference's expanding
radial rosettes, branching edges, drifting focus and softly bleeding colors.
The source is generated inside Studio; the reference video is not the output.
Then add restrained, independently adjustable audio connections and save a
portable local demonstration with its soundtrack.

## Visual construction

- A reusable Radial bloom generator: nested radial detail, petal count, flow,
  expansion, branching, rotation, center drift, palette, color drift, softness,
  grain and light. Preserve circles when changing canvas proportions.
- Continuous nonuniform expansion with evolving contours and scale levels,
  avoiding a rigid spinning star or a repeating texture pasted behind it.
- Use the existing finishing effects where appropriate. Keep all new modules
  disabled in existing presets and preserve their ordering, seeds and pixels.
- Compare sampled frames and motion against the opening of the reference,
  iterating on both the geometry and its temporal behavior.

## Audio scope

First B2/B3 slice: one B1 soundtrack feeding continuous band-energy responses.
Each saved connection has a stable track ID, target, low/high Hz, amount,
sensitivity, attack/release and enabled state. Supply Bass/Mids/Highs/Full
presets, custom Hz bounds, response meters and global bypass.

Apply bounded additive changes over the existing animation. Connections to the
same target sum before clamping; they never enable an effect. Zero amount or
bypass exactly restores the visual base. Monitor volume and export selection
do not affect reactivity. Start with radial expansion/detail/light and a small
set of existing continuous effects; no timebase or playback-rate targets.

Decode and analyze in cancellable workers. Cache bounded derived responses by
source identity, analysis version and authored settings. Responses are sampled
against absolute project time, including trim, offset, loop and silence; seeking,
preview resolution, skipped frames and range exports must agree. Clear errors
replace silent fallback when active mappings need unavailable media.

Mappings participate in Save/Open, Undo/Redo, snapshots, detailed copies and
portable Studies. Reactive documents use schema 5; B1-only and visual documents
retain their existing schemas. Audio dependencies invalidate visual caches only
when they can affect pixels.

## Ownership and delivery

1. Root: visual generator, effect/Study registration, iteration, Studio lifecycle,
   cache integration, local demonstration and release.
2. GPT-6.1 Sol: audio analysis, mapping validation, compilation, rendering/export
   integration and signal/timing tests.
3. GPT-6.1 Sol: compact mapping editor and Soundtrack entry point, with widget tests.

Validate frequency isolation with known tones, silence and cancellation, random
seeks, offset/trim/loop and partial exports, identity changes, exact bypass,
mapping persistence and the unchanged frozen Studies. Inspect the installed
Mac app and export the new example before merging and installing.

Deferred: onset/event triggers, instrument isolation, automatic beats, multiple
tracks, mixing, live inputs and spectrum-drag selection.

## Delivered example and validation

The built-in **Radial / chromatic bloom** is a 12-second editable visual Study.
The local **Radial / audio bloom** demonstration runs for the selected soundtrack's
24 seconds at 720 × 1280 / 30 fps. Its portable Study includes a local copy of
`reference-study-v01.wav`. Neither the reference nor this user-owned audio is
bundled with the application or committed to Git.

The example uses three restrained responses: 40–180 Hz expands the crowns,
180–2500 Hz increases their detail, and 2500–12000 Hz lifts light. Amount,
Sensitivity, frequency limits and Rise/Fall remain editable through
**Soundtrack… → React to audio…**. Three visual passes refined the alternation
between branching crowns and quieter rays, center drift and soft cyan/rose color.
This reproduces the reference's broad visual language, not its exact frames.

Validation covers known frequency bands, silence, stereo cancellation safety,
trim/offset/loop timing, random seeking, range exports, source identity changes,
cancellation, exact bypass, persistence and stale-worker rejection. The combined
feature/regression run passed 234 tests with one skip. Frozen Study comparisons
passed unchanged; source-region regressions passed all 12 tests. The complete
24-second MP4 was rendered and its video/audio durations verified.

Installed-app QA also exposed a responsive parameter-layout feedback loop and a
soundtrack timeout that treated delayed readiness as a permanent failure. These
are corrected with focused regression coverage: size measurement no longer
rebuilds the parameter layout, and valid late audio readiness can recover while
real decoder errors remain explicit.

The rebuilt Mac app was verified with the selected WAV: soundtrack readiness,
waveform, playback and changing response meters all worked. Paused idle CPU
returned to about 1% after the layout fix. A further 76 parameter/audio tests
passed (one optional native smoke skipped in that run); the separate native Qt
smoke and 11 soundtrack integration tests passed. Rejected replacement audio
now preserves the current track and reports incompatible frequency limits.

## Bass-disruption refinement — 0.11.1

Keep the original local example and save **Radial / bass disruption** separately.
It retains the same 24-second soundtrack and radial source. Bass at 25–100 Hz
drives Frame jitter strength with an 8 ms rise and 65 ms fall; 40–180 Hz drives
Tape damage mix with a 5 ms rise and 75 ms fall, plus restrained color separation.
The source expansion responds slightly faster while the mids/detail and
highs/light mappings retain their previous settings. These are energy responses,
not new onset detection or authored beat events.

Expose Frame jitter strength and Tape damage mix as reusable audio targets for
any source, including effect instances. Both use zero base intensity in the demo
so the extra treatments recover during silence. An opt-in Tape damage Fault
edges mode extends edge pixels to avoid exposed blank bands during tracking
slips; default rendering remains unchanged. All effects and mappings remain
editable in Studio.

## Clarification: vibration inside the rays — 0.11.2

The requested movement is in the rays themselves, from their shared origin,
rather than a shake of the whole image. Add an opt-in angular deformation to
Radial bloom: a traveling wave bends each ray along its length while retaining
radial distances and the center. Integer angular harmonics vary the phase between
ray groups without opening a seam. The existing center drift remains independent.
Controls expose intensity, oscillation speed, wave length and ray independence.
Zero intensity follows the previous rendering path exactly.

The local **Radial / vibrating rays** example starts from the original audio
bloom, retaining its three responses and adding 25–100 Hz → Ray vibration.
It contains no frame-jitter, tape or RGB-separation additions from the preceding
variant. The traveling phase is procedural; audio controls its amplitude. This
is not a physical wave simulation with delayed audio at each distance.
