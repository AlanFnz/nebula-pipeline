# Text / one more try

Reference-13 reconstruction added in 0.41.0, optically refined in 0.42.0,
reframed for complete lettering in 0.43.0, and expanded with brief optical
silhouettes in 0.44.0, and refined final ink in 0.45.0 and 0.46.0.
Load **Studies → Text / one more try**.
The current revision (0.47.0) is an editable 720 × 406 composition at 30 fps,
lasting exactly 450 frames / 15 s. Its 73 authored cuts are independent clips.
The film texture updates at 15 fps. No source-video frames are required to render it.

## Visual and editing decisions

Keep the original wording and the sequence of four-line condensed typography,
pink/monochrome exposures, dark interruptions, red word builds, pale lettering
on black and large final words. The main readable arrangements are:

- JUST / ONE / MORE / TRY
- SOMEONE / TO / BELIEVE / IN
- & YOU KNOW
- I NEED / SOMEONE TO / BELIEVE IN
- & / YOU / KNOW

The original reference lasts 27.77 seconds. At the user's request, condense its
largely unreadable 1.5–16.5 second interval into three seconds of selected optical
interruptions. Keep the opening and closing timings, shifting the closing
sequence twelve seconds earlier. The result is a reconstruction with bundled
Anton and Archivo Black, procedural film texture and selected typographic
interruption inserts; it is not a pixel-identical copy of physical print defects.

The current revision keeps complete words inside the frame, including rotated
inserts and the final enlarged cuts. It reserves room for weave and local ink
displacement. Rotation is authored on the Text source before rasterization;
rotating an already cropped source cannot restore its missing letters. Film
gates remain open in this recipe, while exposure trails can still reach the
edges. Pale lettering uses low erosion and fine grain instead of dark pitting.
The 0.44.0 revision adds five two- or three-frame optical inserts inside the
shortened interlude: a wedge and disc over vertical lettering, a necked round
silhouette, an isolated disc, and a diffuse grey shadow. These recall the
reference around 6–7s and 12.87s. Opening and closing frames, complete lettering,
fine pale ink and the 15.77-second duration were unchanged in that revision. The silhouettes may
extend beyond the canvas and deliberately obscure the lettering behind them.

The 0.45.0 revision lowers ink erosion on the tilted orange IN at 14.67–14.87s,
retaining fine texture and the rest of the montage.
The 0.46.0 revision applies the same fine ink texture to the preceding upright
IN at 14.47–14.67s.

## Editable controls

**Object → Text** owns wording, typeface, line spacing and text layout. The study
opens in **Shots** view: each card shows a thumbnail, wording and duration.
Click to select/preview while keeping the editing scope; double-click or choose
**Edit text** to open Object controls for that clip. Change the wording and press
**Apply main text**. **Duration** below the cards changes only the selected clip
and stretches its optical motion; Undo restores the previous text or timing.
Switch to **Timeline** for proportional durations, drag/reorder, duplication
and automation. Project-level changes still affect the whole arrangement, with
explicit clip overrides taking priority.

The 15-second revision compresses all cut boundaries proportionally to 450 whole
frames, preserving every cut and the closing hold. Each clip references its
original source interval and retains its continuous optical clock through the
existing retiming system. Old single-clip documents keep their original timing
and can still use **Open detailed copy…** for individual internal source cues.
Automatic alternate-phrase adaptation remains future work.
The safe framing is saved as ordinary text size, width, rotation and impression
position values. It does not constrain subsequent edits or automatically fit
replacement text or a different canvas. These controls remain freely editable.

**Effects → Dye transfer** provides:

- Color & light: stock and ink hue/saturation/brightness, uneven exposure,
  edge dye, exposure halo and exposure level.
- Shape & layout: impression scale, position and rotation.
- Optical finish: wet ink displacement, vertical exposure drag, dragged-impression
  strength, softness, edge thinning, erosion, grain and dust. Mottled emulsion
  adds unequal density and rubbed texture; Exposure streaks varies vertical
  density bands; Edge bloom adds a narrow light rim around the impression.
- Motion & timing: gate weave and film cadence. Local registration bends parts of the impression independently;
  Focus flutter varies focus irregularly; Shutter pull drags selected columns
  upward (negative) or downward (positive), leaving a continuous exposure trail.
  These controls can be animated for brief interruptions while readable holds
  keep their own settings.
- Optical silhouette: Off, Disc, Wedge or Bulb; size, width, X/Y position, angle,
  softness and opacity. These darken the printed image before grain and the film
  gate. Size is relative to canvas height (Bulb uses its round base diameter).
  High softness and reduced opacity produce a diffuse shadow. Continuous
  controls support automation; shape changes are editable source cues.
- Film gate: aperture width, horizontal position and edge softness.
- Intensity: dry/wet mix without changing the underlying settings.

Red, pink, monochrome and pale-positive effect presets are available. The effect
accepts any source image, including footage. Bright source pixels are the ink
mask; this is a print conversion. Effect order, project/clip scope, Undo and saved
projects follow the existing app behavior. Continuous visual controls such as
scale, position, drag, exposure and grain are available to automation.

## Implementation and validation

`synth_dye_transfer.py` has no reference-specific text or montage. Absolute-time,
seeded sampling makes seeks reproducible, with no history buffer. Transform and
blur allocations are bounded by output dimensions. `synth_dye_recipes.py` carries
the 73 authored cuts.
The module is appended to the catalog and disabled by default. The current
study is frozen in `presets/text-dye-transfer-v7.json`; the v1 through v6 files
remain intact. All six optical-refinement controls default to zero, so saved
compositions retain the original renderer's pixels. The revised study opts in
explicitly. Silhouette defaults to Off and opacity zero also bypasses it
exactly, without changing random sampling. Other render seeds and recipes are
unchanged.

Coverage includes every authored cue, extreme settings/aspect ratios, random
seeks, retained texture cadence, input ownership, footage, 0/50/100% intensity,
explicit pass ordering including Broadcast wear, save/load, editable wording,
project/clip scope and Undo. Additional comparison checks preserve 72 raw pixel
fingerprints across all 36 pre-existing studies. The delivered MP4 is checked
for complete decoding, 473 frames and agreement with direct frame rendering.
The refinement adds signed shutter/no-wrap tests, zero-control compatibility,
random seeks with the new finish, and original-study pixel fingerprints.
An additional 111-frame comparison covers all 36 earlier studies plus the
original dye-transfer study.
The framing revision additionally checks padded source renders for lost glyphs,
optical-placement margins at all 69 cuts, low dark-pit contrast inside pale
lettering, and retained v2 pixels. Existing saved projects retain their authored
values; load the current built-in study to use the revised framing and texture.

The silhouette revision additionally tests geometry, defocus, opacity, size,
rotation, placement, deterministic seeks, zero-opacity bypass, scoped editing
and Undo. A complete 473-frame fingerprint comparison checks saved v3 output,
with identical opening/closing frames in the revised study.

The built-in study is self-contained and silent. Any reference soundtrack used
for a local demonstration stays separate from the distributable recipe.

The 0.47.0 revision additionally checks all 73 retimed clip states and optical
pixels against v6 at corresponding source times, the exact 450-frame duration,
isolated wording edits, duration undo/redo, save/load, selection scope, and
bounded thumbnail generation. Historic 473-frame checks above refer to v1–v6.
