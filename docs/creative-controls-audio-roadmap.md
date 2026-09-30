# Creative controls and audio reactivity

Recorded: 2026-10-01.
Status: agreed direction, saved for later; these features are not implemented.
Order: independent visual experimentation first, imported-audio reactivity next,
then optional live input. No implementation or scheduled work is started by this plan.

Related work: [effects editor UX](effects-editor-ux-plan.md),
[reusable effects](reusable-effects-plan.md), and
[editing and preview](editing-preview-plan.md).

## Outcome

An artist should be able to choose material, understand what a treatment does,
try variations, compare them and develop a piece without needing an engineer to
construct its recipe. Studies should serve as editable examples and starting
points. Building from scratch should produce something visible immediately.

The effects editor already provides a focused inspector, scope/inheritance
labels, explicit fixed-value overrides, effect discovery and persistent bypass.
The next stage builds a clearer connection between visual intent and controls.
It must retain the terminal visual style and space for the viewport.

## Phase A: independent creative experimentation

### A1. Starting points

- Offer New piece choices: Text, Shape, Model, Video, or Remix a study.
- A fresh generated piece starts with visible material and one simple section.
  Video leads to import; Remix makes a separate editable copy of the chosen study.
- Keep existing Object, Effects and timeline concepts. Avoid requiring the user
  to understand authored states or configure a long sequence before seeing a result.
- Keep total duration derived from the arrangement. Changing the starting flow
  must not introduce a mandatory independent duration setting for existing pieces.

Acceptance: make a visible text/shape/model piece or import a video, add one
image treatment, save it, and reopen it entirely through the interface. Remixing
and saving must leave the original study unchanged.

### A2. Effect-specific creative controls

Provide roughly three to six useful controls for each supported effect. Choose
names and ranges that describe a visible outcome. Start with a small pilot:

| Effect | Candidate creative controls |
| --- | --- |
| Tape damage | Damage strength, fault frequency, fault duration, color bleed |
| Frame jitter | Movement distance, rotation, changes per second |
| Ghosts / trails | Number of copies, copy distance, fading |
| Particle expansion | Expansion distance, outward time, return time, disorder |

These are candidate behaviors to audit against the engine, not claims that all
are already independent parameters. Add a reusable capability when needed;
avoid exposing a control whose label promises behavior the engine cannot deliver.
Frequency, duration and strength must be independently understandable. Output
FPS, source/effect cadence and movement speed remain distinct concepts.

Keep detailed parameters in named groups, searchable and reachable. Avoid a
blanket More/Fewer controls switch or identical generic sliders on every effect.
Explain which detailed properties a creative control influences. A user editing
those properties directly must be able to see any creative adjustment still
acting on them.

Creative adjustments should preserve authored animation. For example, increasing
strength can scale a changing signal around its existing baseline rather than
replacing every frame with a constant. Keep the existing explicit Use fixed value
operation for users who want a constant. Define an appropriate bounded mapping
for each target; do not apply one multiplier blindly to counts, angles and timing.
All new adjustments start neutral on existing studies.

Acceptance: increase an animated effect's intensity while retaining its temporal
pattern; restore neutral and recover the original pixels. Whole-clip and section
scope, inherited values, reset, bypass, Undo/Redo and Save/Open stay coherent.

### A3. Comparison and controlled exploration

- Add named snapshots and A/B comparison at the same playhead time, quality and
  deterministic noise state, so differences reflect the edits being compared.
- Add Vary this effect, with subtle/moderate/strong exploration amounts.
- Let the user keep properties such as palette, object or timing unchanged.
  Show what will vary; record the random seed so a saved take remains reproducible.
- Build on the current New take and Keep mechanisms. Separate temporary auditions
  from committed changes; returning to a snapshot must recover its full behavior.

Acceptance: capture A, vary only the chosen effect, compare A/B during a short
loop, retain B, and restore A without losing other effects or source settings.

### A4. Visual discovery and explanations

- Add short effect/preset previews, preferably on the current material, with
  cached low-resolution results and clear loading/quality feedback.
- Audition before applying; browsing alone must not edit the document.
- Explain concrete reasons an effect may appear inactive: bypass, an inactive
  interval, insufficient bright areas, or a missing required source. Link to
  the relevant control or source choice where possible.
- Give studies a concise editable breakdown. For example: Edge phosphor creates
  the contour; Scan drag creates the streaks; Signal background supplies the grain.
  Clicking a contribution opens its controls and allows comparison by bypass.

Acceptance: audition two presets without committing either, understand an
incompatible or inactive effect, and identify the effects responsible for the
main features of a study. Preview work must yield to editing and export.

### A5. Understandable motion

Add a compact curve/envelope editor for behaviors such as build up, burst, hold
and recover. Show duration and easing directly; offer useful movement patterns
without requiring dozens of sections. Preserve current shared ink timing and
section-resize semantics. Arbitrary per-parameter keyframing is a separate scope
decision, not a prerequisite for the first creative-controls release.

Acceptance: shape a burst and recovery visually, repeat it with controlled
variation, and recover the same movement after saving and exporting.

## Phase B: imported-audio reactivity

Audio drives the same meaningful creative controls established in Phase A.
The study's authored animation remains the base; audio supplies reversible,
bounded modulation. Mapping amount zero or bypass must recover the base result.

### B1. Audio track and synchronized transport

- Start with one imported audio file, a waveform, trim and timeline start offset.
- Support audible preview and synchronized video/audio export, with explicit
  playback volume/mute and end-of-track behavior. Muting monitoring should not
  silently disable analysis or alter an export setting.
- Keep the existing section-based duration calculation. Any action that fits
  the composition to the soundtrack must be explicit.
- Define how the new track interacts with an imported video's existing audio.
  For the first release, provide an explicit soundtrack choice; do not silently
  mix two sources or build a multitrack audio editor.
- Handle missing files with relink and clear state. Follow the existing portable
  study/media policy when saving assets.

Current code already exports imported video audio, including trim, loop/hold
and retimed video clocks, through synth_video_audio.py. Extend that behavior
without regressing it. A separate soundtrack and audible synchronized preview
are additional work; existing audio export is not an audio-reactivity system.

### B2. Analysis and visual connections

Analyze the imported file once, in cancellable background work. Initial signals:
overall loudness, low/mid/high frequency-band energy, and transient/onset strength.
Sharp-hit detection should not be presented as reliable instrument separation
or perfect beat/BPM detection.

Offer useful mapping presets, followed by editable connections:

| Audio feature | Example visual target |
| --- | --- |
| Bass energy | Particle expansion or object scale |
| Sharp hits | Tape faults, flashes or sudden displacement |
| High-frequency energy | Grain or jitter |
| Overall loudness | Glow or brightness |

Each connection shows its audio feature, target, input meter and resulting value.
Expose amount, sensitivity, attack and release, plus appropriate output limits.
Attack controls how quickly the visual responds; release controls how gradually
it settles. Provide individual mapping bypass and a global audio-modulation bypass.
Allow several connections over time, with an explicit rule for multiple
connections targeting the same property; avoid silent last-writer behavior.

Start with continuous targets with clear semantics. Triggering a complete
expansion/glitch gesture from a hit requires event/envelope behavior; merely
scaling its distance must not be labeled as triggering a burst. Add such targets
incrementally after deterministic continuous modulation works.

### B3. Deterministic time and export

- Resolve analysis and attack/release envelopes against composition time, not
  the number or order of preview frames rendered. Scrubbing to a time must give
  the same result as continuous playback and export at that time.
- Cache analysis using source identity, analysis settings and an analysis-version
  key. Store authored connections/settings in the document; caches must be
  regenerable and must not become a hidden dependency of the artwork.
- Respect audio offsets, trims and exported ranges. Section loops and reordered
  sections must have a documented relationship to the soundtrack's continuous
  clock. Do not restart audio because a visual section repeats.
- Low preview FPS must not change the timing of the finished piece. Show preview
  performance honestly; reuse the preview preparation/cache foundation.
- Keep modulation of shared durations, source playback rates and other timebase
  controls outside the initial target set to avoid feedback into their own clocks.

Acceptance: create a bass-driven expansion/intensity example and a loudness-driven
brightness example; verify repeatable frames at selected timestamps, seek behavior,
audio/video alignment and matching results after Save/Open. Cover silence, short
tracks, trim/offset changes, section loops, range exports, missing media and
cancelled analysis. Bypass returns the original study exactly.

## Phase C: live input, later

After file-based reactivity is reliable, investigate microphone and system-audio
input, device selection, latency and dropout handling. Live capture and export
reproducibility need a separate design, likely recording the incoming audio or
control signal. No hardware is required for the imported-file milestone.

## Implementation boundaries and preservation

- Preserve all existing study pixels, renderer compatibility versions, defaults,
  parameter IDs, source clocks, effect order, framing and export behavior when
  new capabilities are absent or neutral. Do not replace pixel baselines.
- Keep creative/audio controls reusable across compatible studies and materials;
  encode required capabilities rather than branches for individual study names.
- Use stable target IDs and documented units/ranges. Define evaluation order and
  composition with local overrides before choosing a schema. Treat offset,
  scale, bounded remapping and event triggers as distinct operations.
- Store new authoring data separately from existing recipe values so comparison,
  Undo/Redo, bypass and neutral restoration remain reversible. Use optional,
  versioned additions; old documents load without new behavior.
- Preserve two-decimal presentation, known units, non-editing scroll gestures,
  accessible controls and explicit scope. Keep previews responsive and cancellable.
- Reuse the composition/compiler, effect metadata, parameter widgets, study
  persistence, preview scheduler and video-audio export boundaries. New analysis
  and modulation code should be independently testable; do not place DSP in UI callbacks.

## Delivery order and open decisions

- [ ] First release: A1 starting flow + A2 creative-control pilot + A3 snapshots/A/B.
- [ ] Extend independent experimentation with A4 previews/explanations and A5 motion.
- [ ] Add B1 imported audio/transport, then B2 mappings and B3 export verification.
- [ ] Consider C live input after the file-based workflow is established.

Audio depends on stable creative targets, reversible adjustments and deterministic
preview time. A full general-purpose curve editor is not an architectural
prerequisite; implementation planning can choose its position after the first
creative release is reviewed.

Resolve before the relevant milestone: exact pilot mappings and useful ranges;
snapshot scope/persistence; how direct parameter edits combine with creative
adjustments; multiple-connection composition; soundtrack selection/end behavior;
and the asset portability policy. Keep these explicit rather than treating
suggested UI labels or example mappings as finished specifications.

Deliver each milestone in reviewable commits with targeted behavior tests,
existing frozen-study regressions and visual checks at narrow/normal window
sizes. No version bump, implementation branch, release date, live-input commitment
or automatic follow-up is part of this documentation request.
