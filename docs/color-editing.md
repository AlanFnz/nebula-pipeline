# Visual color editing

Choose **Object → Color palette** for nested gradients, folded rosettes and
printed lattice cells. The eight shared palettes follow the source presets.
Each choice applies its colors in one undoable edit. The gradient stops, cell
faces, paper and eye colors can then be edited individually.

The same names appear in the **Palette**, **Ink palette** and **Filament palette**
menus in Object and Effects. The swatches show the colors that the selected
treatment uses. For example, Neon ridge gives a gradient eight inks and a
filament a fuchsia and a cyan.

In the composition inspector, open **Effects → Dye transfer**. The Background
color and Ink color cards show the color at the preview frame, before texture,
lighting and other effects. Click a swatch or **Choose…** to open the picker.

For a second impression, start with the **Two-color poster** preset or open
**Print mask** in an existing Dye transfer effect. Choose a **Mask shape** and
set **Apply mask to** to **Ink**, **Paper** or **Ink and paper**. The matching
second color swatches appear above the controls. **Rectangle** gives the plate
a width and height. **Straight cut** colors one side of a line. Position
and rotate the plate with **Mask X**, **Mask Y** and **Mask angle**. **Mask
edge irregularity** gives the cut an uneven outline that travels with it.
Use **Animate…** beside the position or angle to move the cut during a clip.

For a **Stepped rectangle**, adjust **Corner cut width** and **Corner cut
height**. **Plate density gradient** varies the second color along the local
vertical axis. Positive values make the lower end denser, and rotating the
mask turns the gradient with it. **Paper & ink** controls the fiber and
the pickup of the two impressions.

The picker supports a visual spectrum, RGB/HSV controls, hex entry, screen
sampling, and a **Swatches** menu. Choose **Project colors** or a shared palette,
then click an individual ink to preview it. Choosing an
existing project swatch copies its exact HSV values, including brightness above
1; simply inspecting a color never quantizes it. A newly chosen RGB/hex color
uses the brightness represented by that color.

**Apply to** defaults to the shot at the playhead when editing the whole project,
or the selected clip when editing a clip. Choosing **Composition** authors a
shared color instead. This replaces the study's color changes in that shared
scope; explicit clip overrides still take priority. Other effects and animation
events are retained. Apply is a single undoable edit; Cancel changes nothing.

The restore arrow removes only that color's three local channel overrides.
For individual numeric edits or animation, expand **Color channels** or search
for Stock hue, Stock saturation, Stock brightness, or the equivalent Ink fields.
Animated ranges are labeled read-only summaries; **Use fixed value** exposes the
normal editable control. Existing studies and render behavior are unchanged.
