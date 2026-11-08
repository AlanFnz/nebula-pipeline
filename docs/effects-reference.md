# Effects reference

[Documentation](README.md) · [Sources and studies](sources-and-studies.md) · [Editing](editing.md#effects-and-animation)

Start in **Effects → Add effect…** (labelled **Add project effect…** in Entire
project). Browse and preview a preset, then choose **Apply effect**. Search finds
both names and descriptions. **How this look is built** explains the current
piece and opens the controls responsible for each contribution.

**Intensity** blends an image treatment with the result without that treatment.
**Bypass / Resume** keeps settings and timing; **Remove** clears the effect and
its automation in the selected scope. The [editing guide](editing.md) explains
scope, order, fixed values, instances and timed automation.

| Look or task | Reference |
| --- | --- |
| Cyan image fragments, scan displacement, phosphors and filmed CRT texture | [Cyan, scan and CRT](#cyan-scan-and-crt-treatments) |
| Compressed rows, folding and unstable signal patterns | [Temporal fragments](#temporal-fragments) |
| Polarity, outages, rolling static and curved glass | [Broadcast wear](#broadcast-wear) |
| Toner printing or isolating video foreground | [Photocopy and foreground](#photocopy-and-foreground-extraction) |
| Keep coarse preview-like texture in full-size output | [Low-res finish](#low-res-finish) |
| Print collage, Film burn, Optical overprint or Contour melt | [Text studies](sources-and-studies.md#text--burning-print) |
| Dye transfer and color picking | [One more try](dye-transfer-study.md#editable-controls), [color editing](color-editing.md) |
| Contact print | [FAC51](contact-film-study.md#source-and-effect) |
| Signal tension | [Tension](sources-and-studies.md#tension--elastic-signal) |
| Color emulsion and Color field | [Prismatic / solid studies](sources-and-studies.md#prismatic-color-film) |
| Print surface and Frame jitter | [Ink and mixed media](sources-and-studies.md#ink-stamps-and-mixed-media) |
| Edge phosphor, Scan drag, Signal background and particle treatments | [Profiles and particles](sources-and-studies.md#profiles-and-particles) |

Portrait studies named below are personal examples, not entries guaranteed in a
fresh installation. Their **Source → Treatment presets** are reusable with your
own video. Reference clips and the owner's footage are not distributed.
Descriptions of frozen earlier variants explain compatibility; the controls
are available in this checkout. No reference screenshots are needed to use them.

## Cyan, scan and CRT treatments

Use **Source → Treatment presets** on imported footage to start from a look.
These presets keep framing and clip timing but replace the composition's effects
and master treatment; Undo restores the previous treatment.

| Preset | Starting look |
| --- | --- |
| Cyan / modulated CRT | Cyan selection, scan displacement, color-lock faults and filmed screen. |
| Cyan / grain CRT | Similar modulation with stronger row lines and fine grain; broad moiré disabled. |
| Cyan / slice screen | Cyan/pink tonal mapping, displaced image strips and phosphors. |
| Cyan / filmed exposures | Brighter highlights, gentler fragments and short exposure fades. |
| Cyan / fractured CRT | Strong phosphor surface, solarized relief and broken negative patches. |
| Cyan / CRT bars | Cyan-exposure bars with stronger phosphors and independent square flashes. |
| Cyan / unstable CRT | Varied event timing, nonlinear bar travel and tape tears. |

For row visibility use **Screen mesh → Row depth / Row spacing**. For grain in
the bright image use **Raster / grain → Fine grain / Horizontal grain**. For
noise in dark areas use **Signal background**. New footage may need different
signal-selection thresholds.

Two reusable effects are available with footage, text and generated objects:

- **Scan modulation** selects the whole image, highlights or a color range.
  **Signal selection → View → Selection** displays the key; hue tolerance,
  minimum brightness/saturation, softness, inversion and a directional fade
  control its coverage. **Original source** samples pixels before cutout and
  color treatment. Scan structure controls row spacing, irregularity, oscillator
  displacement, tearing and trails. Signal colors, color failures and bright
  points are independently editable. Modulation speed zero freezes the effect
  while the footage continues; Modulation FPS zero gives continuous oscillators.
- **CRT capture** adds full-canvas phosphor columns, curved and uneven camera
  moiré, raster instability, lens softness, focus breathing, light spill and
  light-dependent grain. Capture drift speed zero freezes the screen behavior;
  Capture FPS zero gives continuous drift. Interference uses reference-space
  distances and fades subpixel phosphors in small previews.

These are image treatments inspired by analog signal manipulation and filming a
CRT, rather than a circuit-level simulation of a particular television. Both
are opt-in, have an exact Mix = 0 bypass, and reproduce the same state on seeks.

**Source → Treatment presets → Cyan / slice screen** applies an editable cyan
and pink display treatment to any imported clip. It combines three optional
effects with the existing color separation, bloom, raster and frame jitter:

- **Chroma print** maps source tones to colored mids and pale highlights. Black
  and white points, exposure, local contrast, separate warm accents and optional
  solarization control the result without requiring a face or segmentation.
- **Slice echo** displaces horizontal pieces of the actual image. Adjust slice
  count/height, horizontal and vertical displacement, magnification, reshuffle
  interval, travel, independent motion FPS, tint, exposure and Screen overlap.
  Zero motion FPS gives continuous travel between deterministic reshuffles.
- **Screen mesh** adds tilted, gently curved phosphor columns, RGB subpixels,
  fine rows and light-sensitive grain across the entire canvas. Spacing,
  angle, curvature, grain, softness and texture FPS are editable; zero texture
  FPS freezes the screen. Small previews filter subpixel lines while preserving
  mean exposure and color balance.

Chroma print and Slice echo work on generated objects and text as well as
footage. By default they process the source before image finishes; Screen mesh
finishes the result. Each has a neutral Mix = 0. Custom project order can change
the image-treatment chain.

**Slice echo** additionally offers **Slice angle**, **Keep bright highlights**,
**Image-shaped opacity** and **Event fade**. The angle changes only the seams;
the brightness mask lets dark fragments reveal the image underneath. Event fade
is the fraction of each reshuffle interval spent fading at either end, on the
same held clock as slice motion. **Screen mesh → Phosphor wear** adds tiny row
registration errors and uneven phosphor points.

**Slice echo → Timing scatter** varies event boundaries around the chosen
Reshuffle seconds. **Travel turbulence** accelerates and reverses individual bars
inside each interval. **Fragment flashes → Flash timing scatter** has its own
rhythm; **Flash source → Before slices** samples the underlying image, including
prior color treatment, so squares remain distinct from the main tinted bars.
The flash duration is capped to its current randomized interval. Timing is
seeded, held by Slice motion FPS and deterministic under arbitrary seeks.
The new controls default to neutral values; earlier recipes retain their pixels.

**Slice echo → Fragment flashes** gives small source fragments their own faster
rhythm. Set opacity, interval, fade-out duration, count, dimensions, broken edges
and negative exposure. Flashes share the main tint/displacement and held motion
FPS, with a separate event clock. Duration is capped at the interval; very short
flashes can fall between sampled output frames. Set opacity to zero to disable.

- **Slice echo → Fragment width** changes full-width strips into bounded image
  patches. **Broken edges** introduces stepped outlines that reshuffle with the
  same seeded event clock; **Negative exposure** reverses only those fragments.
- **Chroma print → Image softness** defocuses the image before color mapping,
  leaving the later CRT surface intact. **Solarized highlight recovery** restores
  white at the solarization threshold while preserving the reversed tones above
  it. It has no effect when Solarization is zero.
- Adjust **Screen mesh → Column spacing / Column depth / Phosphor wear** for the
  CRT surface. High final Raster softness can blur these fine lines away; use
  Chroma print's Image softness when the face alone should be softer.

For rotating the entire footage image, use **Source → Rotation**. Positive
values rotate clockwise; scale stays uniform and foreground masks follow the
framing. Increase Scale if the rotation exposes corners.

## Temporal fragments

**Signal repetition** compresses horizontal samples of the actual image into
moving rows of repeated fragments. Find it under **Add effect → Motion & echoes**.
**Source → Treatment presets → Temporal fragments** combines it with Tape damage,
Raster / grain and CRT capture, keeping your source, framing and clip timing.
The separate **Portrait / temporal fragments** local Study includes a ten-second
source passage and two editable Repeat spacing automations.

- **Signal selection → Region** chooses the whole image, highlights, a color
  range, or **Video foreground**. Foreground uses the existing local macOS mask
  helper; it requires imported video. The other modes also work with text and
  generated objects. **View → Selection** shows the mask before distortion.
- **Repetitions → Repeat spacing** controls density; smaller means more copies.
  **Sample width / Sample position** choose how much source is compressed into
  each copy. Band height, irregularity and row interruptions break up the rows.
- **Motion & timing → Motion speed / Horizontal travel / Row bending** control
  movement independently of footage speed. Motion FPS zero is continuous.
  Outline movement and Outline echoes disturb the selected boundary.
- **Color & light** controls the blue signal, fringe color/width, contrast,
  original detail and brief color-lock slips. **Outside selection** optionally
  replaces the background; replacement zero preserves the unselected picture.
- Repeat spacing, Row bending, Mix, Color fringe and Signal exposure support
  timeline automation. CRT capture controls the final phosphors, focus and grain.

Signal repetition reconstructs spatial folding at the requested time. It does
not store previous video frames. A foreground mask can make the first preview
slower while preparation runs.

**Signal repetition → Motion & timing** also exposes:

- **Band flow** continuously changes the height, slope and spacing of scan groups.
- **Sync loss** briefly opens the dense repetitions into a larger cyan image,
  pulls the contours apart and introduces color faults before recovering.
- **Slip frequency** sets the average number of unlocks per second when Motion
  speed and the composition speed are 1. Their timing and strength vary with
  the seed; zero disables unlocks.
- **Line flutter** breaks up fine contours with fast row slips and interruptions.

Motion speed scales these movements together; zero freezes the effect while
footage continues. Motion FPS holds their shared clock. Band flow, Sync loss
and Line flutter also support timeline automation.  The effect's
**Unstable signal** look enables them on any source; **Source → Treatment
presets → Living fragments** adds the accompanying CRT, tape and grain finish.

To recreate the local Study from another file:

```bash
.venv/bin/python scripts/create_temporal_fragments.py /path/to/source.mp4 \
  --start 6 --save-study --output /path/to/new-output-folder
```

The script saves an editable composition and MP4. With `--save-study`, it also
copies the footage into the local Study library; no source media enters Git.
Add `--living` to create the new variation instead. Choose a passage with visible
subject movement: the effect distorts the footage but does not animate its pose.

## Broadcast wear

**Broadcast wear** is a reusable image treatment for text, other generated
objects and video: shifting color fields in shadows, full-frame static
interruptions, rolling static bands, colored polarity reversals, CRT curvature
and corner shading. Adjust each independently or set Mix to zero to bypass.
It uses fresh procedural noise; there are no tiled or embedded reference frames.
Its **Polarity** tab exposes cycle, phase, exposure overlap and field
misregistration. **Before finishing** reverses the source before grain and tape
processing, so inverted frames retain their texture. **Composite fringe**,
width and color controls follow contrast edges on any source. Final-screen reversal remains available as an alternative.
**Look → Exposure wash** adds fresh uneven illumination, using Field hue and
color spread. **Signal** offers the original Snow and the new Broken sync
texture, static intensity/color, seeded Random outages and Sync tearing during
interruptions. **Interruption timing → Random** replaces the repeating beat
with irregular gaps and occasional clusters. **Interruption interval** is the
average time between starts; **Interruption duration** sets their length, and
**Duration variation** varies that length independently. Random timing uses the
project seed and signal clock, so seeking, preview resolution and export preserve
the same events. Static FPS controls the noise texture, not this event schedule.
Newly added Broadcast wear uses the **Irregular signal** preset. Saved studies
keep **Regular** timing unless you change it in **Signal → Motion & timing**;
switch that control directly to preserve your other Broadcast wear settings.
The **Regular signal** preset and rolling band remain available. Duration zero
disables scheduled interruptions; the separate Random outages control can still
add extra flashes.
**Screen** controls CRT glass, inset and wear, plus highlight-driven colored
halation, radius, hue and threshold. These controls also process imported video;
none require a text source.

## Photocopy and foreground extraction

**Effects → Photocopy** processes either generated artwork or imported footage.
Ink threshold/contrast, toner amount/size, halftone coverage/dot size/angle,
frayed edges, cold ink, uneven illumination and exposure pulses are independent
controls. **Print FPS** controls fresh grain and exposure flutter; **Exposure
cycle** controls the repeating dark pass and light/color movement. Set Dark
exposure pulse to zero to remove the dark interval. Grain is generated anew
across the entire canvas, without wrapping a tiled paper image.

**Effects → Subject cutout** is an optional video source stage, before jitter
and image treatments. Foreground detects prominent objects; People provides a
person-specific alternative. **Crowd** also detects human regions and analyzes
them individually, helping smaller figures survive changes in foreground
prominence. It is slower on the first visit to an uncached frame.
**Mask continuity** optionally fills short gaps from the source frames on both
sides; **Continuity reach** sets that distance in seconds. Both neighboring
masks and their colors must agree before a pixel is recovered. This avoids an
accumulating trail and respects source trim boundaries and held motion frames.
Zero continuity retains the original single-frame behavior.
Adjust silhouette density, original-background
detail, mask cutoff, feathering and expansion. Optional projected shadows use
the same mask; Subject base follows its lowest point, while Canvas plane lets
you place the ground manually. Crowded scenes, motion blur and occlusions can
produce imperfect edges; this is per-frame segmentation, not identity tracking
or a hand-painted roto tool.

Detection uses [Apple Vision](https://developer.apple.com/documentation/vision/vngenerateforegroundinstancemaskrequest)
locally on macOS 14 or later, without uploading footage or downloading a model.
The first visit to a frame takes longer; masks are cached under
`~/Library/Caches/Nebula Studio/masks-v1/` (512 MiB budget). Detection always uses
the same 720 px framed input, so preview and export share the mask. Changing
source framing regenerates the affected masks; changing grain or exposure
reuses them. An empty detection produces an empty foreground mask.

The Mac app build compiles and bundles the Swift helper automatically. For
development, run `.venv/bin/python scripts/build_mask_helper.py` with Apple's
command-line developer tools installed. Photocopy works without this helper;
only Subject cutout needs it.

## Low-res finish

**Effects → Add effect… → Low-res finish → 360 px preview feel → Apply effect** keeps
the texture of the 360 px preview in a full-size export. Choose the project
scope to apply it throughout, or choose **Editing: Clip** for a local treatment.
**Working resolution** sets the longest edge of the internal raster; the saved
canvas supplies its proportions. **Resolution preset** offers 180, 240, 360, 480,
720, 1080, 1440 and 2160 px without typing. It changes only Working resolution;
sampling, intensity and other effects stay as authored. Manual values remain
available and show as **Custom** when they do not match a preset. These are
longest-edge pixel sizes, not video-height labels such as 720p; the working
resolution is capped at the canvas size. **Enlargement → Soft** smoothly enlarges the
grain and softened edges, while **Crisp pixels** preserves hard pixel edges.
The 180 px, 720 px and crisp 240 px looks provide other starting points.

This renders sources, grain, backgrounds and sequence transitions at the chosen
resolution before scaling the finished frame. Preview resolution changes only the
monitor size when the effect is on; the artistic raster stays the same in the
preview and export. Export MP4 still writes the full canvas dimensions. The
effect saves with the document and supports clip overrides, Undo/Redo and
detailed editing. It is off in existing studies; disable it to restore native
rendering. Working resolution is capped at the saved canvas size.
