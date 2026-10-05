# Creative controls and audio reactivity

Recorded: 2026-10-01.
Status: A1 starting points, A2 creative-control pilot and A3 snapshots/controlled
exploration shipped in 0.3.0 on 2026-10-02. A4 visual discovery shipped in
0.4.0 on 2026-10-02; A5 timed gestures shipped in 0.5.0 on 2026-10-04.
Reviewed against 0.6.1 on 2026-10-05. Audio reactivity remains unimplemented.
Expanded: 2026-10-01 with selectable frequency ranges and future multitrack routing.
Order: independent visual experimentation first, imported-audio reactivity next,
then multiple imported tracks and optional live input. Future milestones do not
start automatically; no scheduled work is configured.

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

Implemented: **New piece…** in the toolbar and **File → New piece…** (Command-N)
opens a compact material chooser. Text accepts wording; Shape offers a rectangle,
ellipse, circle or polygon; Model offers a solid Doryphoros silhouette or particle
head. Generated pieces use the current canvas dimensions and Timeline FPS,
start with one six-second section and open Object controls immediately. Their
source values are embedded in the ordinary composition document; no renderer
or study defaults change. These pieces have no added image treatments: use
Effects → Add effect… to begin building them, then resize/add sections as usual.

Video uses the existing import flow, including the footage's native canvas/FPS
and Source controls. Remix opens an editable copy with the study's saved canvas
and timing. Cancel leaves the current document intact, and replacement retains
the existing Save/Discard/Cancel guard. New generated pieces remain unsaved
until Save; remix edits never overwrite the library study.

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

Implemented pilot: Tape damage, Frame jitter, Ghosts and Particles now have
**Creative** and **Parameters** tabs. Creative edits relative adjustments;
Parameters edits the underlying values, retains explicit Use fixed value and
shows any creative adjustment still acting on a control. Particle models also
reach Creative through **Object → Creative motion…**; Source controls opens
Parameters.

| Effect | Delivered controls | Engine limits made explicit |
| --- | --- | --- |
| Tape damage | Tracking & dropout strength, Pattern change speed, Color bleed | Cadence changes the pattern; it does not independently set fault probability or duration. |
| Frame jitter | Movement distance, Turn jitter, Pose change speed | Movement preserves the X/Y balance; cadence holds each pose and does not alter Timeline FPS. |
| Ghosts | Add / remove copies, Trail distance, Trail brightness | Counts add an integer offset, bounded to 1–10. Brightness retains trail fading; the luminous form companion remains one ghost. |
| Particles | Expansion distance, Outward time, Return time, Path disorder | Release distance needs a released cloud/cycle; stage durations apply only in Impulse mode and retain its cycle-relative caps. |

Most controls scale their affected values within each parameter's engine bounds;
100% is neutral. Copy counts use an additive integer offset, with zero neutral.
The compiler resolves geometry/Finishing, fixed effect parameters, then creative
adjustments for each source state. It preserves activation, cues, seeds, canvas,
source clocks and total arrangement duration. Existing authored zeros stay zero;
adding intensity does not implicitly enable a source or start a burst.

Optional version-1 `creative` data lives alongside an effect's fixed `params`,
separate from the source recipe. Local keys override whole-clip keys; an explicit
local 100% (or zero copies) cancels that inherited adjustment. An individual
restore arrow or Restore creative controls removes only local creative edits and
follows the parent again. Restore this effect removes its whole scoped entry.
Preset replacement uses neutral creative values in a section with an adjusted
parent. Bypass retains these values; Undo/Redo, Save/Open and detailed copies keep
the result. Untouched documents receive no new fields and neutral values recover
the original pixels.

Ghosts gains a reusable Trail brightness base parameter for whole-image copies.
Its default 1 preserves the old arithmetic exactly, and existing fading across
the copies is retained. Independent tape fault probability/duration and a new
trail decay curve are not claimed by this pilot; they need separate engine work.

Inspector base values are collected within the compilation pass, avoiding a
second full arrangement compile for adjusted/bypassed controls. They are not
exported metadata. Tests cover active animation, neutral restoration, fixed base
edits, scope inheritance, source replacement, bypass, history, portability and
frozen-study pixels.

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

Implemented: **Snapshots…** beside View zoom captures complete named compositions
inside the current document (up to 32, without nesting libraries). The library
supports comparison, restoration and removal. Restore retains the library and
is undoable; removal is also undoable. Save/Open retains all source settings,
effects, canvas, timing and seeds. Save as study packages the video dependencies
of both the working piece and its snapshots, copying shared files only once.

**Compare with B** previews the selected snapshot as A. Compact A/B buttons beside
the viewer switch versions at the same absolute playhead, canvas and preview
quality, including selected-section loops. An updating label prevents the old
branch's image being presented as the new branch. Both branches share one bounded
frame cache; preparing each reserves at most half its capacity. Worker generation
checks and media fingerprints prevent stale or cross-branch delivery. Zoom and
comparison do not edit the piece; a real edit returns to working B. Export is
explicitly labelled **Export B MP4** during comparison and uses working B.

Different canvas/framing, Timeline FPS, duration or source/effect time maps make
direct comparison unavailable, with an explanation. Restoration remains
available and recovers that snapshot's own coordinates and timing. Comparison
does not resample, reseed or silently retime either version.

**Creative → Vary this effect…** in the four pilot effects offers
Subtle/Moderate/Strong exploration and a checklist of the controls that may vary.
Timing controls start unchecked; object identity, palette, source settings, noise
seed and other effects are protected. Scope follows the current whole-clip or
selected-section setting. Each Try starts from the captured base rather than
accumulating changes. The dialog stays beside the inspector, keeping the monitor
visible, and supplies A/B and play/pause controls for short-loop auditions.

Try renders a temporary B without editing the composition. **Keep variation**
commits one Undo/Redo step; **Discard / close** restores the working piece. Save,
Save as study and export require keeping or discarding a pending audition;
closing/replacing checks the audition before the ordinary unsaved-document guard.
The chosen values, amount, affected controls and exploration seed are saved in
the effect's optional creative variation record. Manual creative edits clear that
record. Existing New variation/Keep controls continue their established broader
Finishing variation behavior.

- Add named snapshots and A/B comparison at the same playhead time, quality and
  deterministic noise state, so differences reflect the edits being compared.
- Add Vary this effect, with subtle/moderate/strong exploration amounts.
- Let the user keep properties such as palette, object or timing unchanged.
  Show what will vary; record the random seed so a saved take remains reproducible.
- Build on the current New variation and Keep mechanisms. Separate temporary auditions
  from committed changes; returning to a snapshot must recover its full behavior.

Acceptance: capture A, vary only the chosen effect, compare A/B during a short
loop, retain B, and restore A without losing other effects or source settings.

### A4. Visual discovery and explanations

Merged through PR #16 and included in 0.4.0. See
[delivery notes](visual-effect-discovery-delivery.md) for actual behavior, native
adjustments, measurements and limits.

Execution specification: [Visual effect discovery implementation plan](visual-effect-discovery-plan.md).
It defines browser/preset auditions, temporary-preview ownership, visibility
explanations, a composition breakdown, work packages and validation gates.

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

Shipped in 0.5.0 through PR #21: section-owned rise/hold/recover
parameter gestures, signed additive change, smooth/linear easing, a draft-first
editor, an accessible event list and compact draggable timeline lane. Gestures
repeat with section/group loops and scale with section resize, while retaining
source/effect clocks, cue animation, Creative controls and bypass precedence.
The neutral signed Tape horizontal pull supplies the initial VHS use case.
See [delivery notes](timed-effect-automation-delivery.md) for shipped targets,
validation and compatibility. Arbitrary keyframe graphs and audio-reactivity work remain
deferred. Follow-up releases add independent Tape damage instances (0.5.1),
canvas-filled pulls (0.5.2), and timeline section/gesture duplication (0.5.3).

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

Current code already exports each section's imported video audio, including
independent sources, trim, loop/hold, muted gaps and pitch-preserving speed changes,
through synth_video_audio.py. Extend that behavior
without regressing it. A separate soundtrack and audible synchronized preview
are additional work; existing audio export is not an audio-reactivity system.

### B2. Analysis and visual connections

Analyze the imported file once, in cancellable background work. Initial signals:
overall loudness, frequency-band energy, and transient/onset strength. Low/mid/high
presets provide starting points; users can choose arbitrary lower and upper
frequency limits in Hz, either numerically or through a selection on a spectrum.
Show the selected band and its response. Validate limits against the source's
available spectrum and make out-of-range or silent bands understandable.
Sharp-hit detection should not be presented as reliable instrument separation
or perfect beat/BPM detection.

Offer useful mapping presets, followed by editable connections:

The routing model is: **audio track → frequency range or full spectrum →
energy/onset response → visual control**. A range does not identify an instrument;
separate drum/vocal examples below assume the user supplies separate tracks.

| Source | Example analysis range | Example visual target |
| --- | --- | --- |
| Drum track | 40–150 Hz energy | Particle expansion or object scale |
| Drum track | 2–8 kHz energy or transients | Grain, jitter or brief glitches |
| Vocal track | 300 Hz–3 kHz energy | Glow intensity |
| Any selected track | Full-spectrum loudness | Brightness or future word-morph progression |

Each connection shows its source track, frequency range, response type, target,
input meter and resulting value. One track can feed multiple independent
mappings; each mapping retains its own selected range and response settings.
Expose amount, sensitivity, attack and release, plus appropriate output limits.
Attack controls how quickly the visual responds; release controls how gradually
it settles. Provide individual mapping bypass and a global audio-modulation bypass.
Allow several connections over time, with an explicit rule for multiple
connections targeting the same property; avoid silent last-writer behavior.

Start with continuous targets with clear semantics. Triggering a complete
expansion/glitch gesture from a hit requires event/envelope behavior; merely
scaling its distance must not be labeled as triggering a burst. Add such targets
incrementally after deterministic continuous modulation works.

For future word morphing, distinguish Trigger (a detected hit advances to the
next word and starts its transition) from Continuous (audio energy controls
progress between shapes). Trigger timing must remain deterministic when seeking;
define retrigger/hold behavior so bursts of hits do not accidentally skip words.
These are future mapping targets and depend on implementing word morphing.

Design saved mappings around stable track IDs from the first single-track
release. Reordering, renaming or relinking a track must not redirect its mappings.
Spectrum selections and mappings belong to the document and participate in
Undo/Redo, Save/Open and snapshots.

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
cancelled analysis. Also verify selected-band isolation with known test signals,
independent responses from two mappings on the same track, persisted frequency
limits and reproducibility after changing attack/release. Bypass returns the
original study exactly.

### B4. Multiple imported tracks, after the single-track release

Allow several independently aligned audio tracks to drive different effects.
Each track has its own trim, timeline offset and audio level. Give it separate
controls for audible output and visual modulation, so a silent control track
can still drive the image. Distinguish monitor mute from export inclusion;
changing an output level must not silently change modulation sensitivity.

Keep analysis and mapping controls per source track, with visible routing and
per-connection bypass. A track can drive several effects, and an effect can
receive several tracks through the explicitly defined combination rule. Keep
independent track clocks aligned to the composition timeline. Add soundtrack
mixing/export only with explicit levels and inclusion settings, preserving the
existing video-source-audio path and avoiding accidental double playback.

Acceptance: import two tracks, route different frequency bands to different
visual controls, offset one track, and compare/bypass each connection. Muting a
track's audible output must leave its visual response intact; disabling its
visual drive must leave its audible output intact. Save/Open, snapshots, rename,
reorder, relink, missing-media recovery and export preserve track identities,
routing and synchronization. This milestone does not require a general-purpose
DAW, instrument separation or live capture.

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

- [x] A1: visible starting flow, existing editor integration and save/open.
- [x] A2: creative-control pilot with reversible, bounded per-state adjustments.
- [x] A3: named snapshots/A/B and controlled, effect-scoped Keep/Discard auditions.
- [x] A4: previews, explanations and composition breakdown, included in 0.4.0.
- [x] A5: bounded timed parameter gestures and envelope controls; arbitrary keyframes deferred.
- [ ] Add B1 imported audio/transport, then B2 mappings and B3 export verification.
- [ ] Extend to B4 multiple imported tracks with independent routing and explicit audio output.
- [ ] Consider C live input after the file-based workflow is established.

Audio depends on stable creative targets, reversible adjustments and deterministic
preview time. A full general-purpose curve editor is not an architectural
prerequisite; implementation planning can choose its position after the first
creative release is reviewed.

Before the audio milestones, resolve the initial visual targets and useful
ranges, multiple-connection composition, frequency ranges and band filtering,
trigger/retrigger behavior, and per-track soundtrack selection/end behavior.
Extend the existing snapshot and portable-media behavior from A3 and section
footage rather than introducing a separate persistence policy. Suggested audio
labels and example mappings remain proposals, not finished specifications.

Deliver each milestone in reviewable commits with targeted behavior tests,
existing frozen-study regressions and visual checks at narrow/normal window
sizes. Release dates, version bumps, live input and automatic follow-ups require
their own decisions as the work progresses.
