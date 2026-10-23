# Text / burning print

Reconstruct ref-10 as a separate, editable 10.25-second, 12 fps study at 956×720.
The reference combines typographic cuts, red/magenta stock, drifting overexposure,
outlined and reversed ink, gate closures and fine grain. Reference pixels are
used for comparison only; the delivered composition is generated from text.

## Implementation

1. Add Print collage: crop a source window, scale/repeat impressions, overprint a
   larger impression and add angled registration bars. Image treatment, usable
   on text, shapes and footage. No study timing or wording in the renderer.
2. Add Film burn: adjustable print palette, exposure position/width/strength,
   drifting leaks, ink reversal, luminous edges, irregular gate closures,
   softness, grain, dust and cadence. Preserve input colors when color-print
   amount is zero. Deterministic absolute-time sampling for scrubbing/export.
3. Bundle a licensed rounded heavy typeface, without changing existing font
   indices. Author the reference's irregular typography/exposure sequence in a
   recipe and freeze its initial snapshot. Keep Text wording editable.
4. Compare native-aspect frames and the full motion sequence against ref-10;
   iterate exposure, ink, framing and timing. Retain a local comparison and MP4.
5. Verify disabled/zero-intensity identity, generic input, repeatable rendering,
   source-window extremes, study persistence and existing study render hashes.
   Update user documentation, version, build, merge and install.

## Editing contract

Both new treatments expose normal effect controls, Intensity and automation.
Original studies load with new modules disabled and retain their old rendering.
The study's authored cuts remain available via Open detailed copy. Whole-project
parameter overrides replace the corresponding authored values deliberately.

## Delivery and verification

Implemented in 0.28.0. Reviewed reference and generated contact sheets across
all 123 frames, with six optical/type iterations and a final motion render.
The sequence follows the reference's principal cuts and exposure phases;
Fredoka, procedural grain, overprints and gate edges remain an approximation.
The reference media is neither bundled nor needed to render the Study.

Validation: 144 combined effects/text/automation/Study tests passed, followed
by 89 tests on the final renderer/inspector changes (including a new regression
for halos incorrectly brightening flat photographic midtones). All 60 saved
legacy comparison frames were unchanged. The full 956×720 MP4 contains 123
frames at 12 fps. The macOS app built and passed code-signature verification.
