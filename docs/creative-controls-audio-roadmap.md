# Creative controls and audio: current status

Reviewed 2026-11-08 against 0.84.0 / `979d940`. This is a status map, not a release
schedule. The [original roadmap](archive/creative-controls-audio-roadmap-2026-11-06.md)
preserves its proposals, acceptance criteria and earlier priority decisions.

| Area | Status in this checkout | Current reference |
| --- | --- | --- |
| A1: visible starting points | Implemented: New piece for Text, Shape, Model, Video or study remix. | [First piece](getting-started.md) |
| A2: creative controls | Partial by design: Tape damage, Frame jitter, Ghosts and Particles pilot. A universal creative-control layer and independent tape fault probability/duration were not delivered by that pilot. | [Editing](editing.md#variations-and-comparison) |
| A3: snapshots and controlled variation | Implemented: named snapshots, A/B and effect-scoped Keep/Discard auditions. Direct comparison requires compatible canvas and timing. | [Editing](editing.md#variations-and-comparison) |
| A4: visual discovery | Implemented: effect/preset auditions, visibility explanations and composition breakdown. | [Effects](effects-reference.md) |
| A5: motion authoring | Implemented bounded rise/hold/recover gestures for supported controls; arbitrary keyframe graphs remain pending. | [Timed gestures](editing.md#timed-gestures) |
| Reusable effects | Directional regions, independent Tape damage instances and shared project effect ordering implemented. Arbitrary instances for every family remain pending. | [Order and instances](editing.md#processing-order-and-instances) |
| B1: imported soundtrack | Implemented: one track, trim/start/loop, waveform, monitoring and export choices. | [Soundtrack](sound.md#import-a-soundtrack-and-make-visuals-react) |
| B2/B3: audio reactivity | Partial: deterministic band-energy mappings, custom Hz ranges and up to 16 responses. Onset triggers, spectrum-drag selection and broader targets remain pending. | [Soundtrack](sound.md#import-a-soundtrack-and-make-visuals-react) |
| B4: multiple imported tracks | Pending: no multitrack routing or general soundtrack/footage/generated mixing. | [Sound routes](sound.md) |
| V1: first visual sound | Implemented for Pleated field, followed by Chromatic lattice. The proposed Tension sound adapter is still pending. | [Sound](sound.md) |
| V2: reusable sound controls | Partial: versioned instruments, named connections, live audition, mixers, sequencer, save/export and optional layers exist. Arbitrary visual-signal routing is still pending. | [Sound](sound.md) |
| Visual performance | Implemented: recordable common knobs and a Pleated surface adapter. Arbitrary knob assignment and a dedicated curve editor remain pending. | [Visual performance](visual-performance.md) |
| V3: finished-image analysis | Pending: current sound reads supported internal source signals, not arbitrary final RGB images. | [Sound implementation history](visual-sound-prototype.md) |
| DAW connection | Saved Live playback for Pleated and Color waves; optional Ableton instrument recovery. No MIDI Clock/Link/transport or DAW audio capture. | [Live MIDI](../LIVE_MIDI.md) |
| C: live audio input | Pending: no microphone/system-audio input workflow. | [Original proposal](archive/creative-controls-audio-roadmap-2026-11-06.md#phase-c-live-input-later) |
| Preview performance audit | Baseline and diagnosis recorded for 0.48.1. Installed-interaction validation remained open in that record. Later preview/audio/inspector work does not establish completion of every proposed optimization. | [Audit record](preview-performance-audit.md) |

The 0.72.0–0.77.0 UX work is present in the sound session, complete step grid,
Montage selection and block list, Text/Pleated inspector and monitor/export
summary. These bounded improvements do not establish completion of a broader
external UX proposal.

The 0.86.0 pass adds base/monitor value origins, clip-automation and Perform
annotations, recorded/fixed knob labels and a foldable precedence explanation.
It changes presentation only; see [Editing](editing.md#scope-and-inherited-settings).

Status was checked against the source registrations and UI/transport paths,
with focused tests listed in the [documentation review record](documentation-audit.md).
No future milestone dates, work ordering or automatic follow-ups are implied.
