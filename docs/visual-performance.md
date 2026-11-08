# Visual performance

[Documentation](README.md) · [Sound](sound.md)

Open **Perform** in a composition's inspector, or **Visuals**
in **Generated sound…**. Both panels edit the same project immediately. Save the
project to keep those edits. The sound window's **Apply sound** button applies only
the sound draft; closing it does not discard visual edits.

## Playing and recording

1. Choose the preview resolution and **Prepare all video frames**.
2. Play and turn the knobs. Shift-drag makes fine adjustments; the number under
   each knob accepts direct entry.
3. Enable **Record knobs** to record a take. The recording stops when playback
   stops or loops. Recorded controls move on playback and render on export.
4. Command-Z / Edit → Undo restores a whole knob drag, or a whole recording take.
   **Clear recording** keeps the last fixed values; **Reset controls** restores
   the original study. Disabling controls retains all settings and recordings.

A fixed edit to a previously recorded knob replaces that knob's recording.
Recordings use positions relative to total duration; resizing the composition
stretches them. Linear interpolation connects recorded samples. They are stored
in the project, not in an audio file or a preview movie.

## Controls and processing

**Frame** controls scale, horizontal/vertical position and rotation of the
finished image. Rotation preserves pixel aspect ratio. Exposed canvas uses the
frame's average color. **Motion** controls visual pace, acceleration within each
second (Fluidity), centered torsion and evolving irregularity. **Finish** adds
fine grain and hue rotation. These controls are universal: text, objects and
imported video all use the same stage, after their existing effects.

Pace changes the sampled visual clock, wrapping at the end of the source. It
does not change timeline duration or stretch an imported soundtrack. Prepared
frames are indexed by source time; output controls run afterward at the selected
resolution. Preview and export use the same clock and image transformation.
Live playback can still skip frames when the selected resolution exceeds the
machine's processing capacity. Export renders every frame.

**Surface** appears when a supported object is present. The first adapter is
Pleated field: Opening changes aperture, Relief coordinates depth and fold
shadows, and Fold density changes repetition. These are relative to the
existing animated parameter values. They need new source frames and motion
analysis. Surface recordings follow the visual source clock, including Pace;
a recording ends if that clock wraps while recording a surface knob. Source
parameters are clamped to their declared ranges.

When using the layered generated synth, Pleated field analysis still drives the
sound. Pace retimes its control signals; scale, position and recorded motion
contribute approximate framing/motion signals. This is internal motion analysis,
not recognition of arbitrary video pixels. Color and grain do not modulate the
instrument. New signals crossfade into the running voice without resetting the
audio device or playback clock. Surface analysis runs in the background while the previous sound continues.
The [sound implementation record](visual-sound-prototype.md) describes delivery
and buffering changes by version. Other source types gain the visual controls, not
an automatic sound-analysis adapter.

## Storage and extension

Optional `visual_performance` uses schema 7 in compositions and sequences:
`version: 1`, `enabled`, relative `values`, and `tracks` mapping control IDs to
ordered `[duration_fraction, value]` pairs. Fractions are 0–1, values are bounded
by the registry, duplicate/non-finite points are rejected, and a document is
limited to 20,000 recording points. Save/Open, snapshots, undo and compiled
sequences preserve the configuration. Older applications reject schema 7.
Documents without this field, and neutral or disabled controls, preserve the
previous rendered pixels and generated PCM exactly.

`synth_performance.py` declares controls and module-based surface mappings.
Adapters target module IDs (including instances), never study names. A new
adapter can map one control to several parameter deltas/multipliers. The panel
uses that metadata for labels, ranges and visibility. Free assignment of knobs
to arbitrary parameters, MIDI input, and a dedicated curve editor remain future
work; this release records gestures through the panel.
