# Sources and studies

[Documentation](README.md) · [Editing](editing.md) · [Effects](effects-reference.md)

Use **Object** to choose generated material; use **Import video…** for footage.
Changing the generated source keeps treatments, canvas and clip timing. Use
**Studies → Load** for an independent copy of an authored example. The details
below describe controls you can reuse, not prerequisites for a first piece.

Built-in studies are listed in `synth_starters.py` and ship with the app.
Personal studies, local portrait variations and reference movies mentioned in
historical notes are not bundled. The Memory examples linked below are tracked
JSON documents you can open directly. Study names can include a duration suffix.

| Material | Start with |
| --- | --- |
| Text, word reveals and morphs | [Text](#text), [reading print](#text--reading-print), [liquid words](#liquid-words) |
| Strained shapes or moving traces | [Tension](#tension--elastic-signal), [Memory](#memory--afterimage-garden) |
| Luminous grids and folded color | [Lattice](#lattice--chromatic-pulse), [Prismatic field](#prismatic-color-film), [Pleated field](pleated-signal-study.md) |
| Solid figures and imported geometry | [3D models](#importing-a-3d-model), [profiles and particles](#profiles-and-particles) |
| Folding printed cutouts | [Ink stamps](#ink-stamps-and-mixed-media) |

For the current Text and Pleated inspector layout, see [Object inspector](object-inspector.md).
Other focused study notes cover [FAC51](contact-film-study.md),
[One more try](dye-transfer-study.md), [Earth dreams](earth-dreams-print-study.md)
and [Guerrilla Radio](guerrilla-radio-study.md). Earth dreams and Guerrilla are
script-authored personal examples; their reference media is not included.

## Text

Four text studies start with **REVOLUTION IS NOW**. Their image treatments are
also available on other sources:

| Study | Look |
| --- | --- |
| Text / phosphor drift | Green-white type, changing teal/blue exposures and broken sync. |
| Text / pressure | Tall single words, perspective pullback and positive/negative exposures. |
| Text / lost transmission | Repeated word groups, red introductions and chromatic ghosts. |
| Text / night monitor | Smaller white lettering, blue halation and a worn screen. |

The library also retains their **(first version)** entries. Each loaded study
uses its own canvas, timing and embedded recipe.

Choose **Object → Text** to replace a generated source and retain its image
treatments, or load a text Study. Edit **Main text**, then **Apply main text**. Text
supports eight lines and 512 characters. Typeface, size, line/letter spacing,
alignment, color, opacity, intentional width/height stretch and rotation remain
editable. Object X/Y moves the lettering and its source-bound effects. Canvas
resizing uses the existing preserve/fit rules and never stretches the type.
**Text fitting → Fill block** deliberately fits lettering into an authored
rectangle: **Block width** and **Text size** set its proportions. This is separate
from canvas resizing and is useful for very tall, compressed poster type.
**Text copies** and **Copy spacing** repeat the lettering as one movable group.
**Line width limit** uniformly shrinks long groups in Fit long lines mode,
keeping repeated words readable within their intended part of the canvas.
**Wrap after characters** inserts configurable line breaks, preferring spaces
and splitting long words; zero preserves manual breaks. Word reveals still
advance through the original words, and type-on retains the original character
clock and stable layout. **Repeat size floor** reduces duplicate copies before
fitting would shrink the type below the chosen fraction of Text size; zero
keeps all copies. A single copy can still shrink to honor Line width limit.
Lost transmission keeps each word on one centered line, using Text size, Width
stretch and Line width limit to give long words nearly the full canvas width.
Repeat size floor reduces copies when needed, keeping shorter words large too.
Automatic wrapping is off in this study. Its updated layout is frozen in
`presets/text-transmission-v4.json`; earlier snapshots and saved documents
retain their existing layouts.
Six bundled fonts (Archivo Black, Anton, Space Mono Bold, Bodoni Moda, Fraunces and Fredoka) render identically
without depending on installed system fonts; their licenses and pinned source
hashes are in [`assets/fonts`](../assets/fonts/README.md).

**Object → Text → Typeface** also offers the active fonts on your Mac, with
search, family/style names and a preview sample. This works across every text
study, including word morphs, reading montages and subtitles. System styles keep
their installed weight; bundled variable fonts expose Font weight. Existing
studies retain their bundled fonts unless explicitly changed. Missing system
fonts are reported without substituting another font. See
[system typefaces](system-typefaces.md) for portability and supported formats.

**Text / opium · 4.5s** adds a monochrome study with three exposure pulses.
Change **Main text** in **Object → Text**, then press **Apply main text** to replace OPIUM; the bold center and
stretched serif copy share that wording. Its recipe is frozen independently in
`presets/text-opium-v1.json`.

- **Stretch echo** controls the vertical/horizontal stretch, contour or solid
  fill, copies, brightness and color. Its animation can open/reset, breathe or
  hold still. Cycle seconds, starting stretch, easing and Motion FPS control
  the movement. For text, Echo typeface can use another supported font; see
  [System typefaces](system-typefaces.md).
- **Signal etch** controls horizontal grain, edge displacement, erosion and
  scattered light. Solid ink retention protects thick strokes. Exposure pulse,
  Pulse cycle seconds, duration, vertical stretch and spread shape each flash;
  Texture FPS holds only the noise. Set exposure pulse to zero to stop flashes.

Both treatments work on objects and footage as well as text, after the source
generators and before finishing effects. Object position and canvas reframing
keep the echo attached. When combined, the exposure plume follows the original
source so it does not grow with the echo. The two cycle controls are independent;
set both to the same duration and phase to keep opening and flashes synchronized.

**Object → Motion** controls word/character reveals, receding/breathing
size motion, start/end magnification, cycle, acceleration and held motion FPS.
**Perspective pullback** follows a camera-like depth curve, with a fast initial
retreat that settles as the lettering gets farther away.
Type-on preserves the full phrase's layout. Text timing uses the selected scope:
Entire project is the default, and clip overrides are available. Image effects
keep their own clocks. Scrubbing and export need no playback history.

Text is a generated object. Independent text-over-video layers and importing font files through the app remain future work. Active macOS system fonts are supported.

## Text / burning print

**Studies → Text / burning print · 10.25s** reconstructs the typographic cuts,
red/magenta film, light leaks and dark gate flashes of ref-10. It uses a 956×720
canvas at 12 fps and bundled Fredoka lettering. The initial recipe is frozen;
loading it creates an independent editable copy. No reference video is required
or embedded in the Study. Typography and procedural grain approximate the
reference rather than reproducing its original type design or exact particles.

- **Object → Text → Main text / Typeface / Font weight** changes the lettering. The recipe
  alternates uppercase and mixed case; a project-level wording override replaces
  both. Fredoka supports weights up to 700.
- **Print collage** reframes a window of the bright source, scales or repeats it,
  and adds larger/smaller overprints and diagonal bars. Its source window is
  relative to the visible non-black bounds, so replacing the wording may need
  new window positions for isolated letters. It also works on other images.
- **Film burn → Color print** remaps bright source details into ink on colored
  stock. Set it to zero to retain a video's colors beneath the exposure. Film,
  ink and leak hues are independent. Leak position, width, height, drift and
  strength control the light; reversal, luminous edges, ink spread, damage,
  optical softness, grain and dust control the emulsion. Gate opening closes
  the picture into an uneven aperture; zero is fully closed.
- Both effects have **Intensity**, bypass, restore and project/clip scope.
  Animate light-leak strength/position/size, reversal, luminous edges, distortion,
  gate opening or grain; collage width/height/position and overprint strengths
  also support timed automation. Cadence and the project seed make scrubbing
  and export repeatable. The effects' clocks are independent of the source.
- Controls marked **Animated · Study** follow the authored montage. Use a fixed
  value to replace one parameter, or **Open detailed copy…** to edit its cuts.

## Text / reading print

**Studies → Text / reading print · 7s** is the phrase-friendly companion to
Burning print. It shows complete words in order, gives longer words more time,
keeps optical interruptions between reading holds, and ends on the full phrase.

The reading-print study uses moving pink/amber exposures, ink reversals and
optical reframing during holds, with a two-second full-phrase ending.

- Edit **Main text** in **Object → Text**, then press **Apply main text**.
  The reading montage adapts to the phrase, using complete words and letters.
- **Object → Motion → Reading montage** controls **Montage duration**, **Final phrase hold**,
  **Interruption duration / strength**, **More time for long words**, insert type
  (words, letters, or both), and **Montage ending** (hold or repeat). Choose **Show → Reading montage** in Object → Motion to use this mode.
- Montage duration includes the finale. Match the timeline clip duration for
  one complete pass; changing this control does not resize the clip. Hold keeps
  the final phrase visible after the cycle. Long phrases need a longer cycle
  and/or a larger canvas for comfortable reading. The final hold is capped at
  80% of the cycle, and interruptions at 30% of the remaining word sequence.
- **Text size / Line width limit** set the reading size and margins. Whole units
  fit proportionally; short words have a height limit, and explicit line breaks
  are preserved in the finale. There is no automatic wrapping in Reading montage.
- **Print collage → Follow reading montage** centers complete impressions during
  holds and enables overprints during interruptions. **Film burn → Reading
  clarity** reduces occlusion/softness during holds and boosts exposure during
  interruptions; grain, dust and palette keep moving. Both controls are opt-in,
  default off, and have no effect on footage or other text modes. They do not
  protect text from other effects added later in the chain.
- Interruption strength zero retains whole words and suppresses these coordinated
  bursts. The individual effects still have their own Intensity, bypass, scope
  and ordinary parameter overrides. Other typography modes retain their output.
- **Film burn → Timing → Reading print motion** develops the exposure and ink
  within each word's reading time. **Print collage → Timing → Reading reframe**
  adds restrained scale/position changes inside the fitted word bounds. Both
  support automation and require their effect's reading coordination control.
  They default to zero in saved projects from earlier versions; the current
  built-in Study enables them. Set either to zero to quiet that part of the look.
  Film hue, leak hue/position, exposure, softness and grain remain editable.
  The previous frozen recipe remains in `presets/text-reading-print-v1.json`.

## Text / dark optical print

**Studies → Text / dark optical print · 7.5s → Load** opens a separate dark-stock
montage inspired by ref-11. Red enlargements, violet and pale ink, distressed
pigment and circular exposure flashes surround a readable phrase. The canvas is
956×720 at 12 fps. No pixels from the reference video are required or bundled.

- Edit **Object → Text → Main text**, then **Apply main text**. The initial phrase is `REVOLUTION IS NOW`.
  **Object → Motion → Reading montage** controls word timing, interruptions and the
  final full-phrase hold. Longer words receive more time. Explicit line breaks
  are preserved in the finale; increase the cycle for very long phrases.
- **Effects → Optical overprint → Timing → Protect reading moments** coordinates
  the image treatment with those word holds. **Readable hold** sets the fraction
  of each hold that keeps the whole word in frame before enlargements take over.
  Set it to 1 for fully protected holds. The final phrase remains protected.
  These controls have no special behavior on footage or other text modes.
- **Cut rate** makes unequal optical exposures; zero freezes their layout while
  **Print cadence** still advances grain. **Optical movement** changes scale and
  registration; **Focus breathing** softens the unprotected impressions.
- **Fragment montage** replaces the repeated background with varied macro details,
  darker exposures and a second ink impression. **Fragment typeface** can use
  Bodoni or Fraunces for those background details, drawn from the current word;
  the main text keeps its own typeface, size, focus and reading schedule. Footage
  and other sources always use their own pixels. **Exposure halation** adds light
  diffusion to the secondary layers and a pale, brighter flash core.
- Change **First ink hue**, **Second ink hue**, **Pale ink hue**, **Ink brightness**
  and **Stock brightness** for a different palette. **Large impression strength**
  and **scale** control the enlarged source behind the main impression. **Exposure
  flashes**, **Flash size**, **Pigment erosion**, **Film grain** and **Dust & scratches**
  control the optical texture. Flashes avoid the whole word during protected holds.
- Optical overprint also accepts footage and other generated objects, using their
  bright pixels as ink. **Intensity** blends the complete result with its input;
  zero leaves the input unchanged. Main image controls support automation. Protection
  does not undo distortion from other effects or deliberate manual position offsets.
  The optical composition is built before image finishing, so Broadcast wear's
  screen curvature, static and shading affect the background and impressions
  together. Tape damage and CRT treatments also receive the complete composition.

## Liquid words

Choose **Studies → Text / liquid words → Load** for the 6-second, 1000×800 monochrome
word-morphing example. Edit **Main text** in **Object → Text**, then press **Apply main text**.
**Object → Motion → Show → Morph words** enables the same mode on any
text source. Reading time holds each word; Morph duration reshapes it into the
next. Morph easing and Liquid motion control the transition. **Fast attack**
concentrates the morph near its beginning and gives the incoming word more time
to settle. **Elastic settle** makes the strokes flex and recoil without shifting
the whole word. Both are in Object → Motion and default to zero in older files.
The current Study uses a 0.6-second morph with a fast attack, after 1.4 seconds of
reading time. Living strokes adds
gentle bending and swelling during the readable holds as well. Phrase ending can
hold the final word or morph back to the beginning. Spaces and line breaks
separate words in this mode; repetitions and line wrapping are not used.

Object's Text size and Line width limit set the word envelope. Long-word height
can condense long words to keep them substantial beside short words. Zero keeps
uniform fitting. Soft letter shape rounds corners and smooths the merging ink.
Serif weight applies to Bodoni Moda and the bundled Fraunces soft serif; other
fonts keep their own weight. Canvas resizing still preserves the artwork's proportions.

**Effects → Contour melt** independently controls the luminous rims, solid/hollow
breathing, traveling exposure, glow, softness and grain. Its **Contours → Contour
style → Inset ink** adds a dark groove inside the luminous silhouette; Inset
darkness sets its strength. Spacing and exposure drift change its placement and
width. It also works with other shapes and footage, using a luminance silhouette.
The refined Study uses this treatment and Fraunces at weight 900, a wider canvas
and less hollow breathing so thin stems stay visible. **Text / liquid words
(soft motion)** keeps the previous 7.2-second portrait composition; **Text / liquid
words (first version)** retains the original Bodoni composition.
Changing the wording or timing does not resize the timeline: extend the clip to
allow the whole phrase to play. This Study is silent; audio-triggered word
advancement remains planned.

## Tension / elastic signal

**Studies → Tension / elastic signal → Load** opens an original 15-second,
960×720 study at 24 fps. A luminous circular form strains into copper and cyan
filaments, recoils, then gathers while impressions fade. Each gesture changes
its direction, reach, hesitation and recovery. Its outline wanders and the
foreground and residual impressions drift slightly out of registration.
Signal background, Film burn, Color emulsion and Broadcast wear supply a quiet
charcoal/red film floor, moving exposure, grain and a CRT finish.

Open **Effects → Signal tension → Gesture** for the five main controls:

- **Tension:** reach of the pull; zero keeps the input unchanged.
- **Cohesion:** preserve more of the original silhouette or let it fragment.
- **Persistence:** seconds of residual deformation poses; zero removes echoes.
- **Instability:** uneven threads and recoil.
- **Texture:** moving grain within the strained signal.

Further groups expose pull direction, filament spacing/bend, gesture interval,
timing variation, palette, color, glow and highlight selection. In **Motion &
timing**, **Gesture variation** changes the character of each pull; **Filament
flutter** adds irregular movement inside the threads without shaking the canvas.
**Subject drift** lets the figure travel around its authored position;
**Contour wander** loosens the outline, including the faint coherent impression.
**Layer offset** gives the figure, pulled signal and echoes independent small
position/angle changes; **Offset cadence** controls how often these offsets
change.

For the background, open **Film burn**: adjust **Light leak strength** and
**Light leak hue** for its amount and color; **Light leak drift**, **Film
movement** and **Film cadence** control its motion. **Film grain** and **Dust &
scratches** control the film texture. Bypass Film burn to return to the quiet
tape floor below it.
The source shape
stays in **Object → Geometric signal**. Replace it with Text or another object
while keeping the treatments. Signal tension is also available for imported
footage under **Add effect → Distortion**, with three starting presets.

The default Highlights region preserves the dark input floor. When figure
motion is enabled it carries a small dim fringe with each highlight, preventing
a stationary outline beneath the moving form. Whole image
also deforms darker details. Reflected edge sampling avoids introducing black
margins. Persistence samples earlier deformation poses of the **current image**,
not earlier frames of a video; it uses no playback-dependent history buffer.
Project/clip scope, Intensity, effect order, Undo/Redo and saved compositions
use the existing editor behavior.

## Memory / afterimage garden

**Studies → Memory / afterimage garden → Load** opens a 15-second, 720×960,
24 fps piece. A luminous ring draws changing loops while its earlier positions
drift into overlapping amber, coral and turquoise traces. It needs no external
media. **Object → Image memory** exposes the main exploration controls first:

- **Persistence**: seconds of remembered motion. Zero leaves only the current
  object; longer values allow earlier paths to overlap.
- **Drift**: how far deposited traces travel independently of the object.
  Zero leaves each trace at its original position.
- **Dissolution**: how much older traces soften and erode before fading.

Choose a **Sphere**, **Ring** or **Polygon**, then adjust size, path, travel,
motion period, variation and palette. **Horizontal amplitude** and **Vertical
amplitude** independently scale the path: 100% preserves its current extent,
0% stops movement along that axis, and 200% doubles its reach. **Travel distance**
still scales both axes together. These controls move the object and its remembered
positions without stretching their shapes; **Drift** remains separate.

**Object → Center path**, beneath the amplitude controls, balances the figure's
left/right and top/bottom extremes across the current editing scope. It updates
Position X/Y together in one undoable edit. Later amplitude edits retain that
path center. Each slider's maximum is calculated from the canvas, object size,
rotation and the rendered frames of that scope: a centered path reaches both
edges; a manually offset path reaches the nearer edge. The percentage still
means a multiplier of the original travel, so the maximum need not be 100%.
Clip overrides, loops, retiming and preserved artwork framing are respected.
Older oversized values are kept on load; the new limits apply when editing.
Recenter after changing the path, period, size or clip duration if needed.
The bounds describe the current figure before image treatments; drifting
traces, optical glow and VHS distortion may extend beyond them. A stationary
axis or a figure too large/off-center to fit disables that amplitude control;
change Travel distance, center it, or reduce Object size first.

**Source controls…** opens trace strength,
direction, expansion, rotation, color aging, light, softness and glow. Motion
period and Persistence use source seconds at global speed 1; clip retiming and
global speed retime the source and its history together. The history builds
from the start of the source clock, so this study is not a seamless loop.

The memory is reconstructed from bounded samples of the generated object's
past poses: seeking, preview and export agree without warming a feedback
buffer. Image memory generates its own form and traces; it does not
sample the history of imported footage, text or arbitrary 3D models. **Color
emulsion** supplies grain and optical texture; **Broadcast wear** supplies the
subtle screen curvature. Both remain separate, editable effects with Intensity.

**Memory / tape garden** is an independent remix available as
[`examples/image-memory-tape.nebula.json`](../examples/image-memory-tape.nebula.json).
Open it, then use **Save as study…** to keep it in your local Studies library.
It retains the original motion, canvas and duration, combining existing effects:

- **Signal background** raises the blacks into a green-gray tape-noise field.
  Background level, Fine grain and Horizontal grain control its presence.
- **Ghosts / trails** adds short horizontal echoes around the remembered forms.
- **Tape damage** adds restrained tracking slips, line jitter and color delay.
- **Raster / grain** and **CRT capture** add scan lines, phosphor texture,
  optical softness and a little screen instability.
- **Broadcast wear** adds curved glass and brief, irregular static interruptions.
- **Color emulsion** keeps a light optical texture without masking the tape grain.

Each treatment can be bypassed or reduced with its own **Intensity**. The echoes
and object history suggest feedback; this remix does not add a recursive camera
feedback buffer. It uses existing renderers and leaves the original study intact.

**Memory / unstable tape** ([openable composition](../examples/image-memory-unstable-tape.nebula.json))
pushes the object's tracking slips, line jitter, color delay and short echoes
further while retaining the same background texture and remembered motion.

**Broadcast wear → Signal → Band motion → Irregular passes** replaces the
continuous rolling noise stripe with seeded, uneven arrivals and quiet gaps.
**Band interval** sets the average time between arrivals; **Band travel time**
sets the typical screen crossing time (shorter is faster). **Band variation**
varies width, opacity, travel time, easing and direction. Zero variation retains
irregular arrivals with uniform downward passes. **Rolling static height** and
**Static intensity** still control the band's overall size and strength.
These passages are independent of the full-frame interruption schedule.
The previous **Continuous sweep** mode keeps **Static roll speed** and exactly
preserves existing projects. All times follow global source speed; static FPS
changes the noise texture's cadence without rescheduling the passes.

## Lattice / chromatic pulse

**Studies → Lattice / chromatic pulse → Load** opens a 20-second, 720×1280,
30 fps Study inspired by the luminous grid reference. The grid stays fixed
while diamond-shaped waves change each cell’s size and color. It is generated
entirely in Nebula; the reference video is not embedded or needed at playback.

In **Object → Chromatic lattice**, choose Circle, Square, Diamond or Polygon
(3–12 sides). Cell spacing controls density; Maximum size and Minimum size
control the pulse range. Square and polygon shapes stay inside their cells
when rotated. The Wave shape can be diamond rings, circular rings or parallel
bands; Band angle appears only for parallel bands.

In **Free optical** timing, **Pulse period** controls size timing and **Color cycle** controls color timing,
independently of Timeline FPS. Lower periods are faster. Pulse depth 0 holds
cell size; global Speed 0 freezes the source. Choose one of four palettes and
adjust Color wave depth, Color across each cell, saturation and brightness.
Glow amount/spread, the luminous rim, optical softness and fine grain remain
separate controls. Source controls exposes the complete parameter set, including
Mix. **Color timing → Musical phrase** instead uses Tempo and Phrase length;
see [color-wave sound](sound.md#chromatic-lattice-color-wave-voices).

The default size wave repeats every five seconds and the color cycle every ten;
the grain changes continuously. Export and preview evaluate the same absolute
clock. Changing the canvas preserves shape proportions and reveals or crops the
grid around its center; Object position moves the grid and wave center together.

## Prismatic color film

**Studies → Prismatic / color film → Load** opens a 15-second, 720×1280 optical
Study. Opposing color planes turn, fold toward a thin edge and gather into a
triangle. It is generated entirely inside the Studio, with no reference footage
or external assets required. The Study is silent and its recipe is frozen.

**Object → Prismatic field** replaces another generated source while retaining
its treatments. Scale, Polygon sides and Gather into shape control the subject:
zero Gather opens the planes beyond the canvas, and one makes a closed polygon.
**Final shape** chooses Triangle, Square, Diamond, Pentagon, Hexagon or Circle.
Choose Custom polygon to expose Polygon sides. **Final placement → Canvas center**
centers the visible bounds of the gathered figure, even when changing shape or
rotating it; shared Object X/Y still adds your chosen offset. Keep hinge position
retains the original placement. The revised Study ends centered with no hinge drift.
**Source controls…** exposes Plane opening, Fold depth/cycle/phase, Starting
angle, Turn speed/variation, Hinge drift and Edge ribbon. Palette, Color phase,
Color drift and Color clouds animate the color independently of the geometry.
Edge ribbon follows the evolving fold silhouette as it gathers, including at
small scales and with every final shape; it does not leave a diagonal across
the exposed background.
Fold shading keeps the outer seam while its central hinge shadow fades as
Gather into shape increases. The closed figure has no residual center crease.
The Study authors the larger turns with transitions; Turn speed adds continuous
rotation. **Transition easing** gives authored turns and folds a stronger
acceleration and a longer landing. **Turn settle** adds a small rotational
follow-through before arriving at the target. The Study varies gesture durations
and uses both controls; zero retains the old interpolation. These controls leave
color and emulsion clocks alone. **Prismatic / color film (first version)** keeps the earlier choreography.
See the changelog for rendering compatibility changes in 0.18.0 and 0.19.0.
Setting a parameter in Entire project overrides that parameter's
recipe animation. Canvas resizing reveals or crops the field without stretching
its subject. Shared Object X/Y moves the hinge and attached treatments together.

**Effects → Color emulsion** is a separate treatment usable on generated
objects, text or imported video. Optical softness, Color bleed, Color
registration and Dark edge control the filmed edges. Grain amount/size/color,
Grain cadence and Exposure flutter control the surface. Grain cadence holds
only the grain; it does not slow the folds. Mix blends the finish with the
untreated image. This treatment runs late in the existing image chain and
before any added Tape damage instances and master adjustments.

## Color film / rotating die

**Studies → Color film / rotating die → Load** opens a separate 15-second,
720×1280 Study with a centered, rounded white plastic die over moving optical color clouds.
Color emulsion gives the background and solid the same softness, color fringes
and grain. Broadcast wear adds the curved screen edge; its interruptions are
disabled in this Study. The existing Prismatic Studies retain their rendering.

**Object → 3D solid** chooses a **Die** or an unmarked **Cube**. Size, starting
turn/tilt/roll, three rotation speeds, Turn variation and Perspective are editable.
**Corner radius** rounds the actual geometry; zero keeps sharp edges. **Material**
chooses Optical color or White plastic. The latter has soft studio reflections;
**Surface roughness** changes their spread and **Reflection strength** their amount.
The dots belong to each face and rotate with it; Dot size and Dot brightness
appear for Die only. **Dot recess** adds shallow cavity shading to white plastic
without changing the silhouette. Opposite faces sum to seven. Shared Object X/Y
moves the solid without moving its background. Source controls opens the full
material settings, face shading and opacity; Optical color also exposes palette,
color drift and surface clouds. This source generates its own geometry and needs
no external model file. The visual reference is a
[rounded white plastic die](https://www.boardgamesmaker.com/print/round-corner-dice-16mm.html).

**Color film / rotating die (optical color)** is the separate colored, sharp-edged
variant in Studies.

**Effects → Color field** controls the independent background: Palette, Color
phase/drift, Color clouds, Cloud size/motion, Saturation, Exposure and Mix.
**Object → No object** leaves the background and finishing effects visible.
The field also works behind other generated objects; opaque full-frame sources
may cover it. It is not an imported-video overlay. Canvas resizing reveals more
background while preserving the solid's proportions and reference size.
Preview, scrubbing and export use the same absolute animation clock.

## Importing a 3D model

In **Object → 3D solid → Shape**, choose **Imported model**, then **Import model…**.
Choose a static **GLB** or **glTF 2.0** file. For glTF, keep any companion `.bin`
files in the model folder or its subfolders. Geometry is centered, uniformly
normalized and embedded in the project; after saving, the original files are
not needed. Saved Studies and snapshots also contain the geometry.

**Replace model…** changes the figure while keeping its size, position, rotation,
material and treatments. **Clear** removes its geometry; Undo restores it. Use
Scale and the shared Object position controls to frame it. Starting yaw, pitch
and roll set its angle; each axis has its own rotation speed, with zero stopping
that axis. **White plastic**, **Optical color** and **Black glass** are the Studio materials;
Color emulsion, grain and other effects can treat the model and background together.

**Model height** stretches an imported figure along its own vertical axis while
keeping its width and depth fixed. Size still scales the entire model uniformly.
For **Black glass**, Surface roughness and Reflection strength control the studio
highlights. Glass transmission controls how much background shows through;
Glass refraction distorts that background within the object. This is a
screen-space glass approximation, not a physically traced glass volume. Zero
transmission makes the object opaque.

This importer supports static geometry with up to 60,000 triangles / 180,000
vertices and files plus buffers totaling 64 MB. It preserves scene transforms
and smooth normals, but uses Studio materials instead of the model's original
materials or textures. Export rigged or morphing objects as a baked static mesh;
export compressed geometry without Draco or meshopt. Embedded animation is not
played.

## Ink stamps and mixed media

For an Ink stamps source, **Object → Motion & timing…** exposes the gesture as four durations in
seconds: **Unfold**, **Stay unfolded**, **Fold**, and **Stay folded**. Timing is
**shared across all clips**, including when a clip is selected. The first
edit establishes one complete timing profile and continuous clock; changing
clips then shows the same values. Shape, inks and other appearance effects
keep their existing clip controls. Use **↶** to restore a timing value from
the base recipe, or **Restore recipe timing** to return the original motion.
Save/open, Undo/Redo and detailed copies retain the settings.

Clips that already span complete ink cycles resize together when timing
changes, retaining their cycle counts. Boundaries round cumulatively to export frames without adding drift.
Manually arranged clips that do not span whole cycles keep their lengths;
the shared motion clock continues through their boundaries. Old saved timing
overrides are consolidated: project timing wins, otherwise the first clip
with custom timing supplies the common profile. The embedded source is retained.

**Gesture speed** scales this motion independently: 2× runs twice as fast, .5×
runs at half speed, and 0 freezes it. Durations are measured at 1×; the inspector
shows the resulting loop length at the current speed. The turn is retimed with
the opening and closing so the same edge-on views survive a fast unfold. The
figure can keep turning during a fully open or closed hold. Stay folded is the
total rest between gestures, split around the loop boundary in the recipe's
original proportion. Zero-duration stages are instantaneous; all four at zero
hold the closed pose.

**Motion FPS** controls how often the geometry updates, independently of
**Gesture speed**: at .1× and 15 Motion FPS the figure still gets 15 poses per
second, with smaller movement between them. For smoother motion, raise Motion
FPS and **Timeline FPS** beside Canvas in the workspace header together (for example, both to 30 fps).
Lower Motion FPS deliberately retains the mixed-media holds. **Frame jitter → Jitter
FPS** independently controls how often the tiny positional shakes change; 6–8
FPS gives longer holds than 15 FPS. Print/background noise also keeps its own
clock. **Arrange** controls custom clip and clip lengths. **Timing**
includes cycle phase and automatic/manual cycling; the original percentage
settings remain in the detailed editor.

**Studies → Ink bloom** creates a 3.53-second, 15 fps study from one editable
clip. Select **Output canvas → Square** for its reference framing. Seven ragged
cyan, magenta, yellow and white impressions unfold into a rotating cluster,
pass through edge-on views, and fold back into a compact stamp. The shapes and
paper are generated procedurally; no reference footage or downloaded textures
are needed by the app.

Two independent effects are available in every composition:

- **Ink bloom:** stamp count, size, spread, point count/depth, shape irregularity,
  ink palette and split colors. Grouped Look and Timing controls expose opening/closing timing,
  cycle phase, signed turns, tumble, tilt, individual fanning, cluster depth,
  closed-stack spacing, middle folding, reverse-side ink, perspective and position. **Automatic cycle = 0** makes
  **Opening** a manual control. Motion FPS holds the geometry independently of
  export FPS; rates are measured at global speed 1.
- **Print surface:** paper and ink grain, ink wear, frayed edges, held scan
  registration, rotation jitter, persistent fibers, broad paper mottling, fresh
  texture boil, dust and scan softness. It treats the combined image, so it can
  also be applied to the head, rays and other sources. **Mix = 0** is an exact
  bypass. Scan FPS sets its own cadence at global speed 1.

Ink bloom now uses **Print surface → Background → Frame noise**: a fresh
full-canvas grain field and new density patches on every held scan frame, with
no translated texture or wrapping. Background noise, Noise size, Noise clumping
and Background tone are independent of the figure's ink treatment. The source
and its softened edges are protected while the surrounding background changes.
The noise remains deterministic when scrubbing or exporting. **Original paper**
retains the previous moving-sheet treatment and is the default for older saved
documents. To update an existing clip, change only Background to Frame noise;
the Chaotic background preset also provides a starting point for new effects.

**Ink bloom → Stamp shape** replaces the figure with a square, circle, triangle,
regular polygon or imported artwork. The original burst remains the default.
The animation uses a stack of flat stamps: one central impression and surrounding
copies overlap, unfold in 3D, turn and gather again. Replacing the silhouette
keeps that motion, the selected ink palette and the independent print background.
Shape width, height, rotation and polygon side count are in the Look tab's shape controls.

Use **Custom artwork → Import…** for a transparent PNG cutout or a contrasting
image (PNG, WebP, TIFF, JPEG or BMP). Transparency supplies the silhouette; for
opaque artwork, choose light areas on dark or dark areas on light. Holes and
partial transparency are retained. Import selects Custom artwork automatically.
The figure is recolored with Ink palette; source RGB colors are not retained.
Empty margins are cropped, proportions are preserved, and masks over 2048 pixels
are reduced on import. The processed silhouette is embedded in the document, so
save/open, detailed copies and export work after moving the original file.
Switching to a built-in shape keeps the artwork available. Imports and edits
support Undo/Redo and clip overrides; ↶ restores the inherited artwork.

**Frame jitter** is a reusable effect for the ink figures, particle head and
other generated sources. Apply **Hand-positioned paper**, **Subtle scan** or
**Loose cut-paper**, then set Horizontal/Vertical jitter, Rotation jitter,
Scale jitter, Jitter FPS and Jitter strength. Position values are pixels at a
720-pixel short edge and scale with the preview/export canvas. Each held frame
gets a bounded pose around the authored position; the figure never drifts away
over time. The advanced Jitter seed changes its movement independently of the
source and print textures. Jitter strength = 0 bypasses exactly; Jitter FPS = 0
freezes the pose. The renderer places this effect before bloom, raster and print
finishing, so fresh print background noise retains its own frame pattern.

**Studies → Mixed media / two bursts · 7s** opens a 106-frame, 15 fps composition
with two editable clips and Frame jitter enabled. The second gesture opens
wider, fans out, adds depth/tilt and turns in the opposite direction. A short
parameter transition starts while the first gesture is closed. Replace its
Stamp shape or import artwork to reuse the full motion.

The shorter canvas edge controls stamp size, preserving proportions across
formats; paper covers the whole canvas. Source and treatment settings use the
project/clip scopes described in [Editing](editing.md).

## Profiles and particles

**Studies → Profile / phosphor scan · 4s** creates a 61-frame study at 15 fps,
with a fixed left-facing human profile and four editable clips: Green lock,
Overload, Red hold and Lower scan tear. It uses the existing CC0 head mesh;
no frames or textures from a reference GIF are bundled. Low-res finish renders
at 480 px before enlarging to the saved 960×540 canvas.

- **Object → Model silhouette** controls the head model, uniform scale, angle,
  tilt, roll, framing, neck extension/fullness and contour softness. The mesh has no
  automatic rotation. Shared Object X/Y places the complete source group.
- **Effects → Edge phosphor** turns a source into a dark silhouette with a
  colored backlight and contour echoes. Edit backlight hue/saturation/strength,
  grain, reach, contour width/glow, fringe color/gap, lower fade and silhouette
  fill. Light side selects a left- or right-facing contour; Source threshold
  controls the source mask. Phosphor FPS sets the held texture cadence.
  **Look → Canvas coverage → Extend to canvas** continues the backlight
  above and below the object when resizing reveals more space. The model and
  its contour keep their size and proportions.
  **Region → Profile preset → Neck dissolve** fades the model's bright neck edges and
  softens the silhouette into the backlight below the jaw. It follows model
  framing, scale, roll and Object X/Y. Both profile studies enable it; set it
  to 0 for the previous outline. Saved clips keep their setting (0 if absent).
  In **Region**, choose **Object** for a reusable fade attached to the source,
  or **Canvas** for a fixed viewport region. Adjust Fade strength, Fade start,
  Fade width, Fade direction and Light blending. The same Region page exposes the
  object anchor, region X/Y and linear/smooth curve. Object units follow the
  source's scale; canvas units are half its shortest edge. This blends contour,
  fringe, echoes, fill and backlight at their original stages, before final
  texture. Missing object anchors are identified in the inspector.
- **Effects → Scan drag** stretches the source's bright colors into scanlines.
  Fine streak density/reach, overload strength/position/thickness/exposure,
  tracking tear count/height, irregular row groups, overload bloom, chroma slip, grain,
  softness, direction and fault FPS are independent. Recording width controls
  black side margins in the original canvas; set it to 1 for a full-width signal.
  **Canvas coverage → Extend to canvas** lets streaks and
  overloads reach the resized canvas edges instead of clipping at the original
  recording width. Choose **Artwork bounds** in either effect to retain its
  former framing. Both effects default to extending into the newly revealed
  canvas, including in saved profiles. Native landscape renders stay unchanged.
  A blank image never
  gains luminous bars. Mix = 0 bypasses either treatment exactly.
- **Effects → Signal background** fills the deepest blacks, including the
  silhouette and recording margins, with Refined signal's faint green tint,
  fine grain and horizontal noise. Background level, Fine grain and Horizontal
  grain control its presence; Green tint, Chroma noise and Scanline depth shape
  its color and texture. Shadow reach limits it to dark pixels so bright
  contours remain untouched. Background FPS controls its held cadence (0 freezes
  it); Mix or Background level = 0 restores the original black. The texture
  covers the whole canvas and stays in place when the object moves.

Profile studies use Signal background. Add it in Entire project to fill the
deepest blacks in an older document.

**Studies → Profile / signal echoes · 8s** adds a separate 120-frame variation
at 15 fps. Six clips progress through Green lock, Overload, Red / falling scan,
Violet echoes, Flare / signal rupture and Green return. The second half brings
in **Ghosts / trails**, **Exposure flare** and **Signal drift**, with a brief
violet pause and a return to the initial green palette. All six clips keep the
same fixed head pose and Signal background settings. Edit each effect at Entire project or Clip scope; changing clip durations updates the total.

**Studies → Profile / clear silhouette · 8s** keeps that choreography in a
separate variation, with a slightly larger profile, tighter glow/fringe and
quieter scan streaks between overloads. **Object → Facial definition** emphasizes
the nose, lips and chin before projection; 0 preserves the original geometry.
The study uses an explicit object region for the neck blend.

**Studies → Profile / Doryphoros · 8s** uses a CC0 museum scan of the classical
Doryphoros head with the clear silhouette variation's six-clip treatment.
Facial definition and neck fullness start at zero to retain the scan's profile;
the reusable directional region blends the neck into the signal. Select the mesh
independently through **Object → Head model → Doryphoros**, or use it as a particle
target through **Object → Attractor → Doryphoros** in any particle study. Pose,
scale, Object X/Y, canvas framing and treatments remain independent controls.
The mesh has 32,000 triangles and needs no additional runtime dependency. Source,
CC0 license and reproducible preparation are recorded in
[`assets/models/README.md`](../assets/models/README.md). Previous studies and models
keep their original settings.

### Particle motion

**Studies → Particle head** loads Particle signal: dots gather into an anatomical
head, rebound and dissolve toward a luminous band. Its three clips combine
continuous motion with signal treatments. **Original particles** retains the
first one-clip study.

**Expand / orbit** is a two-clip, 15-second variation with two expansions. The
assembled head turns at 18°/s; the released cloud revolves at 24°/s, then gathers.
A shared centered axis and carried orbit rotation keep the head turning forward
as it reforms. Tape faults deform the image after the strongest outward move.
Use the independent controls below to change those relationships.

You can also choose **Object → Particle model** in any generated composition.

- **Motion → Surges** adds **Acceleration**, **Arrival disorder** and
  **Overshoot**. Groups hesitate, arrive on curved paths at different times and
  rebound before settling. The cycle's timing drifts continuously. **Gentle**
  offers the earlier motion.
- **Motion → Impulse** separates the movement from the hold. **Expansion seconds**
  and **Gather seconds** set the outward and inward durations, while **Motion peak**
  shapes the speed curve: 0 is linear; higher values ease into a narrow velocity
  peak and ease out again. The example uses a .75-second expansion, a 1-second
  return and a .8 peak. **Cycle seconds** controls repetition independently.
  Expansion/gather durations cap at 25%/20% of the cycle to leave room for holds.
  Arrival disorder adds a small stagger without changing the number of cycles.
  **Orbit degrees / sec** and **Orbit after expansion** are available in
  the particle effect's **Parameters** page; use **Find a control…** to locate them.
- **Assembly** sets how tightly particles follow the invisible surface.
  **Assembly cycle** controls automatic gathering and release; set it to **0**
  to hold Assembly at a fixed value. **Cycle seconds** sets the period at global
  speed 1, and **Cycle phase** changes the starting point. This motion lives in
  the effect; it does not require extra timeline states. The inspector displays
  the cycle's settings, not its instantaneous computed assembly value.
- **Release → Expand / orbit** chooses the new outward motion. **Dispersion**
  sets its spread, **Orbit degrees / sec** sets cloud rotation (negative reverses
  it), and **Orbit after expansion** delays spin-up until the field opens out.
  The example uses 24°/s and a 70% threshold. Orbit slows as particles gather;
  **Turn degrees / sec** separately rotates the entire target and field.
  **Cloud / band** restores the earlier release and its **Collapse to band**
  control. Collapse is ignored in Expand / orbit, which has no downward pull
  or funnel taper. Release and orbit settings can also be overridden per clip.
- **Particle count**, **Dot size**, **Dispersion** and **Turbulence** set density,
  texture and the released field. **Parameters** includes collapse toward a
  horizontal band, rotation, tilt, scale, position, perspective, surface relief,
  see-through depth, spectral color, shimmer and scan registration.
- **Human head** uses an anatomical head/neck mesh derived from MakeHuman's
  CC0 base asset, sampled uniformly by surface area. Geometry and interpolated
  normals provide the facial detail; the solid mesh is never drawn. The 94 KB
  asset is bundled for offline use. [Provenance and license](../assets/models/README.md)
  include its pinned source and extraction script. **Stylized head**, **Sphere**
  and **Ring** retain their earlier procedural surfaces. Custom imported meshes cannot be particle targets; import static geometry
  through 3D solid instead. Physical collision/gravity simulation is not included.
- **Portrait head** adds the source's eye surfaces and a smooth subdivision pass.
  The separate 454 KB mesh keeps the earlier Human head asset unchanged.
  **Surface occlusion** under Parameters hides deeper points behind the
  assembled face using a fixed proxy depth grid. It fades away as particles
  disperse; only points are rendered. Older documents default to zero occlusion.
- **Turn timing → Assembled only** eases the head turn to a hold during release,
  keeping **Turn degrees / sec** independent of **Orbit degrees / sec**.
  **Rotation axis → Centered** aligns both volumes to a common vertical pivot;
  its reference population is fixed, so changing Particle count retains identities.
  **Neck feather** softens the lower edge of head targets and restores those dots
  during expansion. These controls are under Particle attractor → Parameters;
  old documents keep continuous turning, the original origin and no feather.
- **Return rotation → Carry orbit** gives the head and cloud one accumulated
  orientation. The head reforms at the angle reached by the orbit, preventing
  a backward turn during gathering. Particle positions and surface lighting
  turn together; expansion timing and easing remain independent. Older documents
  retain **Original head angle** unless this control is changed.
- **Tape damage** processes the recorded image after its other treatments.
  Tracking slip and line jitter displace existing pixels; Dropouts remove short
  stretches of scanline. Chroma delay and Color bleed lag/smear the source's own
  color, and Head-switch error distorts the bottom edge. Fault changes / sec
  controls its held cadence; 0 freezes it. Mix 0 bypasses exactly. The new study
  has no active rays, slabs or flare generators. Tape damage is off in old presets.
- Combine particles with bloom, raster / grain, color separation, trails or
  signal breakup. The particle source runs before those treatments. Parameters
  support project/local overrides, bypass, restore, undo/redo and save/open.
  **Object → Particle model** controls the model, scale, pose and point density.
  **More object controls** opens its complete inspector, including head turn,
  assembly, expansion and orbit controls.
- **Signal interference** is a separate reusable effect: moving chromatic bands,
  uneven exposure and bent vertical scan strings. Its speed, bending, density,
  contrast, chroma and mix are editable. The Particle signal study also uses the existing
  warp, separation, trails, bloom, raster, brief exposure crests and tracking breaks.
  Released brightness dims particles between bursts. Neither reference video
  pixels nor external services are used by the renderer.

Particle paths use seeded identities evaluated directly from time, so seeking
does not need a simulation warmup. Higher particle counts cost more CPU time.

## Refined signal and detailed editing

Refined signal adds granular halos, ghosts, edge flutter, short noise streaks,
colored ray tails and uneven exposure sweeps. **Texture**, **Instability**,
**Magenta** and **Flares** change these treatments in the current scope;
**Brightness** also affects ray cores. Use the detailed editor for individual
parameters. Approved signal is available as a separate study.

The [approved recipe](../presets/composite-study-15s.json) and
[refined recipe](../presets/composite-signal-refined-15s.json) contain the authored
ray changes, exposure sweeps, fragmented blocks and final return. They are
procedural interpretations; the reference movie is neither required nor bundled.

In the detailed editor, selecting a cue scrubs to its time. **Duplicate state** creates an independent
copy and assigns it to that cue. **Generate variation** changes the selected
state and honors its parameter locks. The **Signal flare** module controls
exposure, position, spread, reach, and fringe; slab controls include split
magenta/white fill, per-frame registration, ghost grain, and a localized signal
cloud. **Signal softness** softens the image before the final raster grain.
These controls also work in standalone presets.
