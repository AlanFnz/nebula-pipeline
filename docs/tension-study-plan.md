# Tension / elastic signal

## Intent

An original 15-second study: a centered luminous shape strains into filaments,
briefly loses cohesion, recoils and reforms while residual impressions fade.
Unequal holds, accelerating pulls and damped releases give each gesture its own
rhythm. A quiet moving tape floor and restrained CRT finish support the object.

## Development

1. Capture legacy study frames, then prototype contained, organic and fractured
   versions using the same source. Inspect a contact sheet and motion preview.
2. Add an opt-in, source-independent **Signal tension** image treatment. Append
   its module so existing module identities and random seeds remain unchanged.
   Support effect order, project/clip scope, intensity, undo and video sources.
3. Place five controls first: Tension, Cohesion, Persistence, Instability and
   Texture. Expose direction, filament spacing, rhythm, timing variation, palette,
   highlight selection and glow as secondary controls. Shape stays in Object.
4. Freeze the chosen study as a portable recipe. Check replacing its source with
   text and applying the treatment to a video frame. Preserve every old recipe.
5. Verify deterministic seeking, quiet input, zero strength, time continuity,
   bounds, canvas changes and image-pass order. Compare legacy frame hashes,
   export the full study, inspect the UI, then merge and install.

## Rendering contract

- Bounded deterministic elastic deformations of the current image, independent
  of render order or playback FPS. Motion follows the shared effect clock.
- Persistence reconstructs previous deformation poses of the **current input
  frame**; it is not a temporal buffer of previous video frames. No growing cache.
- Default highlight selection keeps the dark tape floor anchored. Reflected
  sampling avoids new black borders when pulling a source that fills the canvas.
- Five bounded echo taps, reference-scaled geometry and adjustable palettes.
- Existing studies and rendering defaults are unchanged; no migration required.

## Delivered direction

The selected version uses a partially filled luminous circle, copper/ice
filaments and a subtle curved CRT boundary on a moving charcoal tape floor.
It includes three starting presets (Organic tension, Held together, Fractured
signal). The same treatment was inspected with two-line lettering as well.

The main five controls open together in Gesture. The other groups stay collapsed
until needed. Source shape and typography remain in Object. The original study
was frozen in `presets/tension-v1.json`; editing it creates an independent copy.

## Organic motion revision

The initial version varied timing but repeated too much of the same gesture.
Revision 2 gives each deterministic event an independently shaped anticipation,
pull, hesitation, release and settling curve. Short snaps, sustained resistance
and second tugs have different duration distributions and asymmetrical easing.
Each event also varies filament direction, density, bend and reach. Continuous
seeded drift adds local flutter; it does not translate the entire canvas.

Gesture variation and Filament flutter live in Motion & timing. Both default
to zero for saved compositions, preserving the original renderer exactly. New
effect presets enable them explicitly. The updated study is frozen in
`presets/tension-v2.json`; revision 1 remains available for reproduction tests.
Existing Signal background and Broadcast wear create a restrained blue/violet
grain field behind the figure, without adding a background-specific effect.

Revision verification: 172 integration tests passed, followed by 51 focused tests
after smoothing the new controls' entry from zero. Tests compare the actual three
study gestures at normalized phase, check direction-change boundaries and
seeking, and exercise extreme parameters. All 72 comparison frames from existing
recipes (including revision 1 of Tension) stayed byte-identical.

## Loose registration revision

Revision 3 makes the coherent silhouette move as well as its elastic filaments.
Subject drift adds slow seeded travel, Contour wander changes both outlines,
and Layer offset gives the core, pulled signal and each echo independent held
position/angle changes. Offset cadence is independent of export FPS and follows
the shared effect clock. Echoes still use bounded earlier deformation poses of
the current input, not previous video frames.

The highlight selection carries its dim antialiased fringe so it cannot leave
an immobile outline behind. The dark floor stays in place. All new motion amounts
default to zero, preserving the renderer for saved projects; revisions 1 and 2
remain frozen. The new recipe is `presets/tension-v3.json`.

The background borrows only a restrained film flavor from ref-12: low red/plum
exposure, moving grain, occasional dust and a quiet gate. It reuses Film burn's
existing controls rather than introducing a study-specific background renderer.
Signal background and the softer blue CRT field remain underneath.

Revision checks cover independent registration, cadence/frozen clocks, moving
dim fringes, continuous drift, extreme canvases, seek determinism, scope/Undo,
intensity, pass order and portable study loading. The focused integration suite
passed 270 tests. All 72 sampled legacy-study frames, including revision 2,
remain byte-identical; fixed image hashes also protect revision 1.
The additional control-UX suite exposed a pre-existing test comparing coordinates
from different parents (fixed Intensity header versus scrolling controls).
Reproduced on the previous main commit, then corrected the test to compare
siblings while retaining all size/bounds checks. The remaining 49 checks passed,
and the corrected case passed separately. Full 15-second / 360-frame export
decodes cleanly, with four encoded samples within 3.42 mean RGB levels of their
preview renders. The installed app and new control group were visually checked.

## Initial verification

- Focused renderer, UI, ordering, study library, discovery and video suite:
  159 tests passed. Independent intensity tests also passed.
- 70 sampled frames from all 35 previous built-in studies remain byte-identical.
- Checked smooth gesture boundaries, irregular timing, seeds and frozen clocks,
  extreme parameters, neutral inputs, intensity, source replacement, order,
  scope/Undo and save/reopen. Short encoded export agrees with its preview.
- Inspector inspected at 1440×900 and tested with a narrow controls column.
- Full 15-second, 960×720 / 24 fps export and packaged-app inspection complete
  the delivery; generated previews stay outside Git.
