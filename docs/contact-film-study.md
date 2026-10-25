# FAC51 contact film

New independent study, `Text / FAC51 contact film`, based on the supplied
`ref-12.mp4`. The target is its FAC51 / THE HAÇIENDA mark, red/magenta exposure,
positive-to-negative transition, black interval and final film transport.
The canvas is 956 × 720. The current study has 96 authored exposures at 12 fps
and lasts eight seconds. Its first 39 frames retain the original reference cut;
the extension adds unequal light bursts, luminous afterimages, longer readable
negative impressions, a short shutter interruption and a final gate slip to black.
The unchanged 3.25-second version is available as **FAC51 contact film (reference cut)**.
This is a procedural reconstruction, not a pixel-exact copy of photographed film.
No video frames, sampled reference textures or original audio are bundled.

## Source and effect

Text → Framed label is opt-in. In **Wording**, enter line breaks for up to eight
main lines; **Label subtitle** accepts up to eight additional lines. Empty subtitle
text hides that block. **Label type fitting → Keep proportions** also removes its
reserved space and preserves the typeface proportions. **Reference proportions**
retains the original condensed FAC51 layout and its reserved subtitle space.

**Frame shape** offers Rectangle, Rounded rectangle, Circle, Square, Diamond and
None. **None** removes the outline while keeping both text blocks; border width
zero does the same. Turning Framed label off returns to the ordinary Wording layout
and hides its subtitle. Horizontal/vertical padding, subtitle size and gap, border
width and rounded corner radius are independent saved controls. Padding and gap
use reference-label units, scaled by Text size. Padding increases the frame around
the lettering; Text size fits the complete label, so the lettering occupies less
of it. Circle/square/diamond enclose the padded text. Explicit width/height stretch
still affects the entire label afterward.

The layout is supported by Whole phrase, One word and Type on, not Morph words or
Reading montage. Defaults retain existing FAC51 pixels; other text studies have
the label disabled and retain their previous layout.

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

Check all 96 frames, including the original four-frame blackout, extended
exposures and final transport. The first 39 frames must match the reference-cut
snapshot. Test random seeking, saved document reload, video input, 0–100% intensity,
explicit order and Broadcast wear on the completed picture. Compare previous
built-in studies against raw-pixel captures before adding the effect.
