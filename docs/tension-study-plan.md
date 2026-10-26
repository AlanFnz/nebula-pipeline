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
is frozen in `presets/tension-v1.json`; editing it creates an independent copy.

## Verification

- Focused renderer, UI, ordering, study library, discovery and video suite:
  159 tests passed. Independent intensity tests also passed.
- 70 sampled frames from all 35 previous built-in studies remain byte-identical.
- Checked smooth gesture boundaries, irregular timing, seeds and frozen clocks,
  extreme parameters, neutral inputs, intensity, source replacement, order,
  scope/Undo and save/reopen. Short encoded export agrees with its preview.
- Inspector inspected at 1440×900 and tested with a narrow controls column.
- Full 15-second, 960×720 / 24 fps export and packaged-app inspection complete
  the delivery; generated previews stay outside Git.
