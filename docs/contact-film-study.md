# FAC51 contact film

New independent study, `Text / FAC51 contact film`, based on the supplied
`ref-12.mp4`. The target is its FAC51 / THE HAÇIENDA mark, red/magenta exposure,
positive-to-negative transition, black interval and final film transport.
The canvas is 956 × 720; 39 authored exposures at 12 fps last 3.25 seconds.
This is a procedural reconstruction, not a pixel-exact copy of photographed film.
No video frames, sampled reference textures or original audio are bundled.

## Source and effect

Text → Framed label is opt-in. Wording, second line, font, size and border width
are saved text controls. The framed layout is a deliberately condensed label;
it stretches the two lines into fixed proportions. It is supported by Whole
phrase, One word and Type on, not Morph words or Reading montage. Existing text
studies have the label disabled and retain their previous layout.

Contact print is a separate image effect available for generated sources and
footage. Bright input supplies the printing mask. It exposes controls for dye
and fringe hue, brightness, light position and size, positive/negative ink,
density, erosion, gate geometry, shutter, grain, dust, softness and cadence.
Its Intensity blends against the incoming image. The authored exposure cuts
live in `synth_contact_recipes.py` and the frozen study snapshot, not the renderer.
Changes made in the inspector override the chosen parameter across the montage;
Restore returns that parameter to the authored changing values.

The whole contact image is composed before screen and tape finishing by default.
With an explicit effects order it follows that order; keep Broadcast wear below
Contact print to bend the complete film image. Existing studies are unchanged.

## Verification

Check all 39 frames, including the four-frame blackout and the last transport
frames. Test random seeking, saved document reload, video input, 0–100% intensity,
explicit order and Broadcast wear on the completed picture. Compare previous
built-in studies against raw-pixel captures before adding the effect.
