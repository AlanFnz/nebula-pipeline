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
