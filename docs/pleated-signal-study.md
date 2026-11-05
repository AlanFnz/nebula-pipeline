# Pleated signal / violet transmission

An editable 20-second reconstruction of the opening movement of `ref-14.mp4`.
The canvas is 960 × 720 (4:3), with the reference's 12 fps visual cadence.
The project needs neither the reference movie nor a soundtrack to render.

## Twenty-second extension (v3)

V3 adds five seconds after the existing 15-second sequence, retaining every
original frame and its timing. The extension continues the mirrored retreat,
rolls through ribbed views, then leaves the mirrors for an oblique camera pass.
A brief settling at the end gives the upcoming sound experiment a release point.
There are 240 frames at 12 fps, with no repeated clip or global slowdown.

The study is still silent. Sound synthesis is the next separate milestone.

## Motion revision (v2)

The first version condensed motifs from sparse stills and interpolated between
poses. It consequently missed the reference's temporal structure. V2 follows
frame observations of its opening 15 seconds: the rapid push at 0.3–0.8 s, pull
back, camera turn, mirrored traveling sheet at 3.5 s, short return/hold at 7.33 s,
four-way view at 8 s, contraction around 8.7–9.5 s and expanding mirrored relief.
Later changes of view occur at 13.75 and 14.58 s.

Camera channels use monotone cubic curves, sampled once per reference frame.
Interior keys preserve velocity instead of repeatedly easing to a stop. Scale
interpolates logarithmically. Optical gate positions during the lateral retreat
and contraction are numeric observations of the reference's visible extents.
All samples are ordinary editable parameter values in a single composition
clip, not video frames or a hidden external animation. Changing a control can
replace that channel while the remaining authored channels keep moving.

## Source and controls

**Object → Pleated field** creates the scene procedurally. Rays intersect a
repeating height field, with the nearest surface supplying occlusion and
shading. The source is deterministic at any playhead position; it does not
accumulate feedback. Intermediate arrays use bounded rows.

The optional **Perspective relief** camera orbits the surface using yaw, pitch
and distance. Mirroring happens before camera projection, so a turn changes
visible faces and depth inside the reflection. Mirror center X/Y reposition
the optical axes. The original optical camera remains available and is still
the default for older projects; its Perspective and Relief view X/Y controls
apply to that original camera model.

- Geometry: four profiles, density, depth, curl, stagger and irregularity.
- Camera: model, scale, angle, orbit, distance, mirror axes and surface travel.
- Field: extent, taper, side placement and diamond/ellipse/rectangle outline.
  The gate can gather the sheet horizontally while its relief keeps moving.
- Timing: source phase, flow and cadence. Camera timing lives in the sequence.
- Color: five palettes, hue rotation, saturation, exposure, highlights,
  perspective-light direction and background drift.
- Finish: optical softness, fold shadows and source opacity.

**Effects → Color emulsion** adds bleed, registration and fine grain.
**Effects → Screen mesh** supplies the phosphor columns and scan rows. Both
remain independent, reorderable effects. The screen texture stays at canvas
scale as the camera zooms.

## Compatibility and verification

The current starter is frozen in `presets/pleated-signal-v3.json`. The earlier
15-second v1 and v2 snapshots remain available; saved v1 projects retain the original
renderer because the new camera is opt-in. No historical palette or profile
was changed. Other study sources and effect algorithms are unchanged.

Tests cover deterministic seeking and save/reload, original camera compatibility,
source replacement and opacity, extreme camera views, field outlines, reframing,
frame cadence, motion beats, curve continuity, preservation of the first 180
frames and exact 20-second export length.
The v1 source was additionally compared pixel-for-pixel against the preceding
release across its three profiles and four mirror arrangements.

The movement is now based on the reference's actual timing, rather than an
invented montage of motifs. Surface topology, lighting and individual optical
distortions remain procedural approximations; this is not a pixel-identical
reproduction of the recording.
