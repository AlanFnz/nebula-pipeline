# Sources and studies

[Documentation](README.md) · [Editing](editing.md) · [Effects](effects-reference.md)

Use **Object** for generated material, **Import video** for footage, or
**Studies → Load** for an editable example. Changing an Object source keeps
its treatments, canvas and clip timing. Loading a study uses its own settings.

Built-in studies ship with the app. Personal variations and reference footage
mentioned in older records may need external files. A study name can include
a duration suffix.

Studies linked to a Live Set carry an **Ableton Live** label. In **Browse**, filter
by Ableton Live or search for the Set's filename. Load the study, then choose
**Open in Live** beside Synthesizer. See [Live MIDI](../LIVE_MIDI.md) to link a Set.

## Text

Choose **Object → Text**, edit **Main text** and press **Apply main text**.
Layout holds size, spacing and position; Motion holds reveals and animation.
**Text fitting → Fill block** deliberately stretches lettering into a rectangle.
Canvas resizing preserves proportions.

Text supports eight lines and 512 characters. Choose a bundled font for easy
sharing or an active macOS [system typeface](system-typefaces.md). System fonts
are referenced, not embedded. Independent text-over-video layers are not supported.

| Study | Starting look |
| --- | --- |
| Text / phosphor drift | Green-white type with broken sync. |
| Text / pressure | Tall words and perspective pullback. |
| Text / lost transmission | Repeated words and chromatic ghosts. |
| Text / night monitor | Smaller lettering and a worn blue screen. |
| Text / opium | Monochrome exposure pulses and stretched lettering. |

For Opium's look, **Stretch echo** shapes the secondary lettering and **Signal
etch** controls erosion and flashes. Both also treat other generated sources
and footage. Their cycle controls are independent.

## Text / burning print

A built-in 10.25-second study of typographic cuts, film exposure and light leaks.
Change Main text to replace the wording. **Print collage** reframes and overprints
the source; **Film burn** controls ink, stock, leaks and gate flashes. Replacing
words may need new collage-window positions. **Animated · Study** marks values
that follow the authored cuts.

## Text / reading print

A seven-second word sequence ending on the full phrase. **Object → Motion →
Reading montage** controls duration, final hold and interruptions. Longer words
can receive more time. Match the clip duration to the reading cycle for a full pass.

**Print collage → Follow reading montage** and **Film burn → Reading clarity**
coordinate those treatments with the word holds. They do not protect text from
other effects added later.

## Text / dark optical print

A 7.5-second word sequence with dark stock, enlarged ink impressions and exposure
flashes. Edit the text and Reading montage timing as above. **Optical overprint →
Timing → Protect reading moments** keeps words visible during holds; **Readable
hold** sets how much of each hold is protected. Stock/ink colors, fragment layers
and flashes remain editable.

## Liquid words

**Text / liquid words** morphs between words. **Object → Motion → Show → Morph
words** enables the mode on other text. Reading time and Morph duration set its
rhythm; Fast attack, Elastic settle and Living strokes shape the movement.
**Contour melt** adds luminous rims and hollow forms.

Extend the clip when adding words or lengthening the cycle. This study is silent;
audio-triggered word advancement is not implemented.

## Tension / elastic signal

A luminous form pulls into filaments and gathers again. **Signal tension →
Gesture** exposes Tension, Cohesion, Persistence, Instability and Texture.
Persistence keeps earlier deformation poses of the current image, rather than
previous video frames. Change its source through Object; the effect also accepts
footage. Tension's proposed sound connection remains pending.

## Memory / afterimage garden

**Object → Image memory** generates a moving Sphere, Ring or Polygon with traces.
Persistence keeps more motion history; Drift moves deposited traces; Dissolution
softens them. Horizontal/Vertical amplitude change path reach. **Center path**
balances the current figure's extremes; glow and drifting traces may extend beyond
those bounds.

This source reconstructs its own object's history. It does not remember imported
video, text or models, and its accumulating history is not a seamless loop.
Two editable examples are tracked separately: [tape garden](../examples/image-memory-tape.nebula.json)
and [unstable tape](../examples/image-memory-unstable-tape.nebula.json).
Open one and use Save as study to keep it in your library.

## Optical relic / green reverie

This 8.75-second study uses a procedural Blender sculpture at 720×960 and 24 fps.
Install Blender 4.2 or newer in Applications, then load **Optical relic** from
Studies. Blender runs in the background; its window does not need to be open.

**Object → Blender scene** controls the sculpture, rotation, camera, material
and stage lighting. **Effects → Optical diffusion** controls soft focus, glow
and fine grain. The scene settings are saved in the Nebula project and support
Undo. Geometry and light edits need new frames; finishing edits reuse the clean
3D frames. Use Prepare range or Prepare all at your selected preview resolution.
Export renders at the canvas resolution, with the same scene and treatments.

Use **Object → Part** to select the pedestal, either hoop, the spindle and
central body, crown, or either pin. **Whole assembly** returns to shared controls.
Each piece has its own position, rotation, scale and visibility. **Independent
motion** adds whole turns around any axis; **Follow assembly** includes the
shared turn. Use **Animate** beside a transform to schedule a change. In
**Material**, turn off **Use assembly material** for a separate color and finish.
Selecting a piece changes no values, and the default study keeps its original look.

Asymmetric edits can require a full turn to repeat, where the original sculpture
repeats after half a turn. For a closed loop, match the clip duration to whole
cycles of the assembly and any independently moving pieces.

The connection supports the bundled parametric sculptures. Importing arbitrary
Blender scenes is not implemented. Other sources do not need Blender.

## Orbital rings / painted motion

An 11.3-second, 720×900 study of five painted rings turning around a central
sphere. It uses the same Blender connection as Optical relic. **Object → Part**
selects any ring, the sphere, pedestal or finial; **Whole assembly** controls
shared geometry, paint colors, landscape, camera and lighting.

**Motion → Poses per loop** sets the stepped rhythm: 60 reproduces the study's
held poses; zero gives continuous motion. **Precessing motion** blends the
authored changes of axis with simple rotation. Select a ring to change its
**Authored orbit** turns, phase and axis tilt, or add your own animated transforms.
**Motion exposure** adds a faint delayed pose. The cycle is about 7.53 seconds;
the default clip keeps the reference's 11.3-second duration, rather than ending
at a complete cycle.

The finish uses **Print surface**, **Optical diffusion**, **Film burn** and **Broadcast wear**.
The current study uses a finer, cleaner pigment finish. Previously saved projects
keep their authored texture settings.
In **Print surface → Surface**, **Painted color** preserves the palette while
adding drawn contours and moving pigment. **Painted shading** and **Paint tone
steps** simplify the lighting. **Contour movement**, **Color misregistration**
and **Exposed paper edges** separate the drawing from its fill. **Pigment
variation**, **Ink grain**, **Ink wear** and **Grain size** control the texture;
**Texture boil** renews it at **Scan FPS**. **Paint loop** repeats that pattern
after the chosen duration; zero keeps generating fresh frames. These controls
also work on other objects and imported footage. The earlier charcoal modes
remain available under **Surface → Charcoal print**.

Within Broadcast wear, **Frame shape → Film frame** selects straight sides and
rounded corners; **Film corner radius** adjusts the rounding. Geometry and lighting
edits prepare new 3D frames, while finishing edits reuse the clean frame cache.
All controls use the same saving, Undo, preview and export paths as other studies.

## Spectral tunnel / luminous ripple

A square six-second study of warm-white lights and cool halos in perspective.
The lights advance from the vanishing point toward the foreground. The
0.4-second cycle repeats seamlessly, including its fine grain.
**Object → Spectral tunnel** exposes light shape, perspective, loop motion and
optical finish. **Loop period** changes speed; **Frames per loop** controls the
stepped cadence (zero gives continuous motion). For a seamless export after
changing the period, use a clip duration containing a whole number of cycles.
**Object → Perspective → Orientation** chooses a horizon on the right or left.
It changes the projected lights and center rail, leaving other effects in place.
Existing studies keep their original right-hand horizon.

## Lattice / chromatic pulse

A fixed grid with moving size and color waves. **Object → Chromatic lattice**
controls cell shape, spacing, size range and wave shape. Free optical timing
keeps Pulse period and Color cycle independent; **Color timing → Musical phrase**
uses Tempo and Phrase length. See [color-wave sound](sound.md#chromatic-lattice-color-wave-voices)
for its generated voices and MIDI route.

## Prismatic color film

Opposing color planes fold into a shape. **Object → Prismatic field** controls
Scale, Gather into shape and Final shape. **Final placement → Canvas center**
centers the gathered figure; Object X/Y adds an offset. Source controls opens
folding, turning and palette settings. **Color emulsion** supplies the optical
softness, registration and grain as a separate treatment. This study is silent.

For folded color with sound, see [Pleated signal](pleated-signal-study.md) and
[Sound](sound.md#pleated-field-drone-and-melody).

## Color film / rotating die

A rotating solid over moving color clouds. **Object → 3D solid** chooses Die or
Cube and controls size, rotation and material. **Color field** edits the separate
background; **No object** leaves that background and its treatments visible.

## Importing a 3D model

Choose **Object → 3D solid → Shape → Imported model → Import model…**. Use static
GLB or glTF 2.0. Keep glTF companion buffers in the model folder or subfolders.
Geometry is centered, normalized and embedded when saved; the original file is
then unnecessary. **Replace model…** keeps framing and treatments.

The limit is 60,000 triangles, 180,000 vertices and 64 MB of files/buffers.
Nebula uses its own White plastic, Optical color or Black glass material, without
importing textures or playing embedded animation. Bake rigged/morphing models to
static meshes and export without Draco or meshopt compression. Black glass uses
an image-based approximation. Imported meshes cannot be particle targets.

## Ink stamps and mixed media

**Ink bloom** unfolds and gathers colored stamps. **Mixed media / two bursts**
uses two clips with different gestures. **Object → Motion & timing…** sets
Unfold, Stay unfolded, Fold and Stay folded. This timing is shared across clips;
Gesture speed changes its speed, while Motion FPS changes its cadence.

Choose a Stamp shape or **Custom artwork → Import…**. Transparency supplies the
silhouette; opaque images use selected light or dark areas. Nebula recolors the
shape with the Ink palette and embeds the processed silhouette. Original image
colors are not retained.

**Print surface** controls paper and ink texture. **Frame noise** changes the
background grain; **Frame jitter** adds held positional shakes independently of
the folding clock. Raise both Motion FPS and Timeline FPS for smoother motion.

## Profiles and particles

**Profile / phosphor scan**, **signal echoes**, **clear silhouette** and
**Doryphoros** combine a fixed head with signal treatments. Model silhouette
controls the figure; **Edge phosphor** lights its contour, **Scan drag** stretches
bright details, and **Signal background** fills dark areas with noise.
**Canvas coverage → Extend to canvas** lets supported treatments fill newly
revealed space. Model provenance is in the [asset notes](../assets/models/README.md).

### Particle motion

**Particle head** gathers dots into a head and releases them. **Expand / orbit**
adds an outward cloud and independent orbit. Object → Particle model exposes
Assembly, Dispersion and the main motion choices. **Assembly cycle = 0** holds
Assembly at its chosen value. Impulse separates expansion and gathering times;
Turn degrees / sec rotates the target, while Orbit degrees / sec rotates the
released cloud. Source controls/Parameters expose the remaining settings.

Particle targets are the bundled models and procedural shapes. There is no
physical collision/gravity simulation. Image effects treat the rendered points.

More study notes: [FAC51](contact-film-study.md), [One more try](dye-transfer-study.md),
[Earth dreams](earth-dreams-print-study.md) and [Guerrilla Radio](guerrilla-radio-study.md).
