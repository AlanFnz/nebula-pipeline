# Text / one more try

Reference-13 reconstruction added in 0.41.0. Load **Studies → Text / one more try**.
It is an editable 720 × 406 composition at 30 fps, lasting 473 frames / 15.77 s.
The film texture updates at 15 fps. No source-video frames are required to render it.

## Visual and editing decisions

Keep the original wording and the sequence of four-line condensed typography,
pink/monochrome exposures, dark interruptions, red word builds, pale lettering
on black and enlarged final fragments. The main readable arrangements are:

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
interruption inserts; it is not a pixel-identical copy of physical print defects
or the reference's brief silhouette inserts.

## Editable controls

**Object → Text** owns wording, typeface, line spacing and text layout. The study
uses authored source cues for different phrases and cuts. A fixed wording change
in the inspector replaces the wording throughout the selected scope; it does not
rewrite this montage into a new arbitrary phrase automatically. Use **Open
detailed copy…** to edit individual cues and their wording/timing. Keep this
reference montage first; automatic alternate-phrase adaptation is future work.

**Effects → Dye transfer** provides:

- Color & light: stock and ink hue/saturation/brightness, uneven exposure,
  edge dye, exposure halo and exposure level.
- Shape & layout: impression scale, position and rotation.
- Motion & timing: gate weave and film cadence.
- Optical finish: wet ink displacement, vertical exposure drag, dragged-impression
  strength, softness, edge thinning, erosion, grain and dust.
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
the 69 authored cuts. `presets/text-dye-transfer-v1.json` freezes this study.
The new module is appended to the catalog and disabled by default. Existing
render seeds and recipes are unchanged.

Coverage includes every authored cue, extreme settings/aspect ratios, random
seeks, retained texture cadence, input ownership, footage, 0/50/100% intensity,
explicit pass ordering including Broadcast wear, save/load, editable wording,
project/clip scope and Undo. Additional comparison checks preserve 72 raw pixel
fingerprints across all 36 pre-existing studies. The delivered MP4 is checked
for complete decoding, 473 frames and agreement with direct frame rendering.

The built-in study is self-contained and silent. Any reference soundtrack used
for a local demonstration stays separate from the distributable recipe.
