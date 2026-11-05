# Pleated signal / violet transmission

A standalone, editable 15-second study of the motifs in `ref-14.mp4`:
oblique repeating folds, rapid changes of distance, mirrored chevrons, four-way
diamonds, a contraction into an orange field, and a return to the relief.
The canvas is 960 × 720 (4:3), with the reference's 12 fps visual cadence.
Only the visual is reconstructed; there is no soundtrack or reference-video
dependency in the study.

## Structure

**Object → Pleated field** creates the entire scene procedurally. Rays intersect
a repeating height field; the nearest surface controls occlusion and shading.
Camera coordinates introduce perspective, slant and optional mirroring.
An independently adjustable field outline exposes the drifting background.
The source is deterministic at any playhead position and does not accumulate
feedback from previously rendered frames. Intermediate arrays use bounded rows.

The recipe contains authored camera poses and ordinary sequence morphs, with
short cuts at changes of mirror arrangement. Scale, camera angle, surface
travel, perspective and aperture remain normal animatable parameters. Editing
one parameter overrides that channel while the other authored channels continue.
Reset restores the recipe for that control.

## Controls

- **Fold geometry:** soft pleats, scallops or cushions; density, depth, curl,
  stagger and irregularity.
- **Camera & mirrors:** scale, angle, perspective, relief view, surface travel,
  and none / top-bottom / left-right / four-quadrant mirrors.
- **Field outline:** visible extent, taper, side placement, and a diamond,
  ellipse or rectangular envelope.
- **Motion & timing:** phase, surface flow and motion cadence. The shared
  speed changes the source clock; camera timing is authored in the sequence.
- **Color & light:** four palettes, palette hue rotation, saturation, exposure,
  highlights and moving background color.
- **Optical finish:** softness, fold shadows and source opacity.

**Effects → Color emulsion** adds local color bleed, registration and fine grain.
**Effects → Screen mesh** supplies the tilted phosphor columns and scan rows.
Both remain independent, reorderable effects with their usual intensity sliders.
The screen mesh stays at canvas scale while the object zooms.

## Compatibility and verification

The new source module is appended to the registry and disabled in existing
presets. Historical recipes and their effect algorithms are unchanged.
The built-in study is frozen in `presets/pleated-signal-v1.json`.
Tests cover deterministic seeking and save/reload, source replacement, source
opacity, bounds across geometries and mirrors, reframing, frame cadence, palette
and geometry changes, and the exact 15-second export length.

This is a procedural visual reconstruction, not a pixel-identical copy of the
49-second recording. Its shorter choreography retains the principal motifs;
fine fold shapes and individual camera moves are authored approximations.
