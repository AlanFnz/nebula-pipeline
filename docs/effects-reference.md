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
| Scan displacement and filmed screens | Scan modulation, CRT capture, Screen mesh, Scan drag |
| Repeated image fragments | Slice echo, Signal repetition |
| Signal faults and unstable motion | Tape damage, Broadcast wear, Frame jitter |
| Printing | Photocopy, Print surface, Contact print, Dye transfer |
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

Random interruption timing varies gaps around the chosen interval. Duration
zero disables scheduled interruptions, but Random outages can still add flashes.
Static FPS changes noise cadence independently. Rolling bands have their own
Continuous sweep or Irregular passes controls.

## Photocopy and foreground extraction

**Photocopy** controls toner, halftones, worn edges and uneven exposure.
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

For treatment-specific examples, see [text studies](sources-and-studies.md#text--burning-print),
[FAC51](contact-film-study.md#source-and-effect),
[One more try](dye-transfer-study.md#editable-controls) and [color editing](color-editing.md).
