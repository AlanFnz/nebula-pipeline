# App icon source

The icon uses the user's Refined signal composition at 11.40 seconds, as shown
in Nebula Studio on 2026-10-01. `source-composition.json` is an independent
snapshot of that project. `frame.json` records the full-resolution frame and
square crop used for the icon, plus its macOS inset and rounded corners.

The crop retains the original color, glow, grain and CRT raster. There are no
new image effects. The app and macOS packager use `assets/nebula-icon.png`.

To reproduce the artwork, load the snapshot with `load_composition`, compile it
with `compile_composition`, and render with `render_sequence_frame` at the time
and canvas dimensions in `frame.json`. Crop that image before scaling it into
the icon's rounded square. Render the complete frame before cropping so the
grain and raster match the selected frame.
