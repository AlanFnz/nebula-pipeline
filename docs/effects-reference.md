# Effects reference

[Documentation](README.md) · [Sources and studies](sources-and-studies.md)

Open **Effects → Add shared effect…** (or **Add clip effect…**), preview a preset
and choose Apply effect. Search matches names and descriptions. Intensity adjusts
the contribution; Bypass keeps settings; Remove clears the effect and its
automation in the current scope. [Editing](editing.md#effects-and-animation)
covers scope, order and animation.

| Look | Effects to try |
| --- | --- |
| Film, ink and optical exposures | Film burn, Print collage, Optical overprint, Color emulsion |
| Luminous letterforms | Stretch echo, Signal etch, Contour melt |
| Scan displacement and filmed screens | Scan modulation, CRT capture, Screen mesh, Curved screen, Scan drag |
| Repeated image fragments | Slice echo, Signal repetition |
| Signal faults and unstable motion | Tape damage, Broadcast wear, Frame jitter |
| Printing | Photocopy, Print surface, Contact print, Dye transfer, Type overprint |
| Strained forms | Signal tension |

## Cyan, scan and CRT treatments

For footage, **Source → Treatment presets** offers Cyan looks. These replace
composition effects and Master settings while keeping source, framing and clips.
Undo restores the previous treatment.

**Scan modulation** selects highlights, a color range or the whole image, then
warps it into scan rows. **View → Selection** shows the affected area.
**Chroma print** maps tones to colored ink. **Slice echo** displaces pieces of the
image; Fragment flashes adds a separate rhythm of smaller patches.

**Screen mesh** adds phosphor columns and fine rows. **CRT capture** adds filmed
screen texture, moiré and focus changes. For softer source details with a sharp
screen surface, use Chroma print's Image softness rather than final Raster softness.

**Curved screen** tilts and curves the image and a wire grid on the same surface.
Grid brightness zero hides the grid; surface brightness, grain and patina control
the dark backing. **Signal etch** can add Organic edges and Traveling highlights
before that projection. Those additions default to zero in existing projects.
Under **Motion & timing**, Surface vibration moves the whole plane, Surface
flutter disturbs it locally, Curvature motion varies its bend and Texture movement
animates its wear. Motion speed zero freezes them. All four default to zero.

Set **Wire grid → Grid geometry → Sphere** for a rigid rotating globe behind the
source. **Sphere rotation** controls radius, speed, axis tilt and initial angle.
Negative Rotation degrees / sec reverses direction; zero stops it. This rotation
is independent of Surface motion speed and does not rotate or distort the source.
Grid spacing and wear also apply to the sphere. Curved plane retains older renders.

## Temporal fragments

**Signal repetition**, under **Add effect → Motion & echoes**, compresses image
samples into moving rows. Repeat spacing changes density; Sample width/position
chooses the source fragment. Band flow, Sync loss and Line flutter disturb it.
Motion speed is independent of footage speed; zero freezes the treatment.
It samples the current image, without keeping previous video frames.

**Temporal fragments** and **Living fragments** are footage treatment presets.
To generate the separate local study and MP4 from your own footage:

```bash
.venv/bin/python scripts/create_temporal_fragments.py /path/to/source.mp4 \
  --start 6 --save-study --output /path/to/new-output-folder
```

`--save-study` also copies the footage into the local library. Add `--living`
for that variation. The owner's portrait reference media is not bundled.

## Broadcast wear

Use Polarity for reversals, Signal for static and interruptions, and Screen for
glass curvature, shading and halation. **Before finishing** applies polarity
before grain and tape; final-screen reversal is also available.

Choose the **Soft CRT** preset for gentle curvature, a drifting shadow tint and
light corner shading. In **Screen → Corner shading**, lower the value to bring
the outer image closer to its original brightness. **Screen curvature** controls
the shape of the frame independently.

Random interruption timing varies gaps around the chosen interval. Duration
zero disables scheduled interruptions, but Random outages can still add flashes.
Static FPS changes noise cadence independently. Rolling bands have their own
Continuous sweep or Irregular passes controls.

## Photocopy and foreground extraction

**Photocopy** controls toner, halftones, worn edges and uneven exposure.
Choose **Fine screened plate** for a continuous angled screen. **Paper stock**
controls the grain and lower-edge tint on the sheet. **Ink deposit** controls
the pigment grain, pinholes and the falloff inside each printed contour.
Set **Print FPS** to zero to hold the impression. To color the plate, place
**Dye transfer** after it and choose the stock and ink colors there. Setting
its **Print cadence** to zero also holds the film grain and registration.

For spot-color work on textured stock, choose **Dye transfer → Dry relief
print**. Under **Paper & ink**, adjust **Paper relief** to bring out the
fiber, then vary **Source ink breakup** and **Second plate breakup**
independently. Where the source ink is thin, you can see the plate beneath
it. Thin areas in that plate expose the paper. **Paper tooth size** sets
the scale of the shared surface. **Plate grain size** can give the second
impression a coarser or finer grain. **Bare paper grain** shows through
where the sheet is exposed.

**Light through ink → Reveal underprint** lets the source ink thin over a
localized area. Set the light position over a letter to reveal the colored
plate where the two impressions overlap. On a single-color print this
reveals the stock. To shade a corner of the sheet, set **Edge exposure
angle** and lower **Edge exposure brightness** under **Color & light**.

**Type overprint** adds editable lettering at a position on the artwork.
Each instance has its own wording, typeface, size, color and intensity.
**Ink grain** varies the coverage inside its letters and **Ink pinholes**
reveals the surface underneath.
The Effects list shows the wording beside each active text plate.
Use **Add another instance** for another text block. Its position in the
effect list determines which subsequent treatments affect the lettering.
When moving a project that uses a custom font, put the original font file
beside the project. Nebula checks the font's saved fingerprint when it opens.

**Subject cutout** extracts video foreground before image treatments. Choose
Foreground, People or Crowd, then adjust cutoff, feathering and expansion.
Mask continuity can fill short gaps; blur and occlusion can still leave imperfect
edges. It does not track identities.

Extraction runs locally on macOS 14 or later and needs the bundled mask helper.
The first preview can take longer while masks are cached. For a source checkout,
build it with `.venv/bin/python scripts/build_mask_helper.py` using Apple's
command-line developer tools. Photocopy works without this helper.

## Low-res finish

Use **Low-res finish → 360 px preview feel** to retain coarse texture in a
full-size export. Working resolution sets the internal raster's longest edge,
capped by the canvas size. Soft enlargement smooths it; Crisp pixels preserves
hard edges. This setting is saved and affects export, unlike Preview resolution.

For color swatches and animated channels, see [color editing](color-editing.md).
