# Reusable effects without changing the existing studies

Status: first milestone implemented; later extractions remain planned.
Baseline: `2f4f8a2` on `codex/synthesizer-v0.2`.

## First milestone delivered

- Nine original recipes and named/default presets are frozen in
  `presets/compat-v1.json`. The regression manifest covers 3,385 frames in 99
  cases: complete native cycles, every supported canvas preset, section
  boundaries, previews, full-size samples and an explicit low-resolution finish.
- Saved documents now carry a rendering version independently of their schema.
  Unversioned documents resolve to v1; new starter copies use v2. The original
  phosphor implementation is retained in `synth_profile_v1.py`. Unchanged
  compiler/render operations remain shared and protected by the baseline tests;
  future changes to their algorithms must retain compatible implementations too.
- `synth_render_context.py` and `synth_source_adapters.py` introduce explicit
  image/context/local-frame inputs. `synth_regions.py` provides directional
  regions; `synth_phosphor.py` consumes them without inspecting source IDs.
  Image-derived coverage remains explicit to preserve the original appearance.
- Effects → Edge phosphor → Region exposes object/canvas anchors, strength,
  start, width, direction, origin, curve and light blending. Profile preset
  retains the existing Neck dissolve control. Choosing a generic region opts
  the edited document into v2; save/load and undo retain the selected behavior.
- Tests compare legacy and generic phosphor before quantization at zero,
  partial and full strength, and demonstrate reuse on geometry and embedded
  artwork. The original nine starters retain their captured pixels.
- A separate Profile / clear silhouette starter uses the new region binding.
  Its optional Facial definition source control emphasizes the nose/lips/chin;
  the existing mesh assets and original starter recipes are unchanged.

Scope: region bindings currently treat phosphor contributions. Source adapters
expose compound root frames, not individual stamp planes or particle frames.
Slab ghosts/halos, arbitrary effect instances, reordered stacks and general
capability-aware source routing are still later milestones. This is a first
working extraction, not a claim that every legacy renderer is now decoupled.

## Goal

Make treatments reusable across geometry, stamps, imported artwork, silhouettes
and particles while preserving every current starter's appearance and behavior.
Keep the current Object / Effects / Timing workflow. Starters should remain
finished artistic compositions with a few useful controls, backed by reusable
operations rather than source-specific conditions throughout the renderer.

Some specialization is appropriate: head pose and neck geometry belong to the
model source; particle attraction belongs to the particle generator. The aim is
to separate these from treatments such as contour color, ghosts, texture and
spatial fading. Not every operation will apply to every source.

## What is coupled today

- `synth_profile._neck_dissolve` searches the full preset for `silhouette`, then
  reads its pose, scale and position. The phosphor renderer uses this region at
  several different stages of contour and backlight construction.
- In `synth_effects`, Ghosts combines a general smear with slab-specific ghosts;
  Granular halo is implemented by the slab source itself.
- `synth_subject` selects objects by enabling source effects. There is no shared
  source output containing a subject mask and its local coordinate frame.
- Render callbacks receive the whole preset. Some treatments infer the subject
  from RGB brightness; source identity and framing rules leak into evaluation.
- Composition macros map to concrete module paths. Starter factories and state
  resolution also consult current defaults. Saving parameters alone cannot
  protect a study from changes to renderer code, defaults or evaluation order.

Existing deterministic rendering and golden-frame tests provide a useful base.
They do not yet freeze every current starter revision: for example, the profile
canvas hashes intentionally exercise the older treatment without neck dissolve.

## Proposed separation

| Part | Responsibility | Examples |
| --- | --- | --- |
| Source | Generate the object and describe its coverage and local coordinates | Shape, stamp, model silhouette, particles |
| Region | Describe where an operation acts, independently of object identity | Directional falloff, radial mask, noisy edge, artwork mask |
| Treatment | Transform an image or an explicitly selected contribution | Phosphor contour, backlight, ghost, scan drag, distortion |
| Recipe | Assemble sources, treatments, regions, motion and artistic controls | Profile / signal echoes, Refined signal, Mixed media |
| Canvas and finish | Own the frame, atmosphere, working resolution and final grade | Aspect ratio, signal background, raster, master adjustments |

### Small shared rendering contract

Introduce a render context with canvas and reference dimensions, explicit object
transforms, continuous and held clocks, and deterministic random streams. A source
can supply its image, subject coverage mask, and local coordinate frame. Additional
data such as depth or geometry are optional, declared capabilities.

Treatments request their required inputs rather than finding another module in
the preset. Preserve image-derived mask extraction as an explicit input option:
silently replacing it with a clean source mask would change existing phosphor
results. Multiple source contributions and ray accents must remain representable;
the new Object abstraction must not collapse an existing compound composition.

Regions and treatments declare object or canvas coordinates. Object-relative
regions follow the object; canvas atmosphere covers the whole viewport. Resizing
the canvas must retain object proportions. A spatial transform must define which
associated masks and coordinates it transforms, so subsequent effects stay
registered to the object. Recipes specify which source/mask a treatment targets.

Use adapters around the current renderers first. Preserve their precision,
sampling, clocks, random sequences and call order. Compute additional masks only
when needed; this is not a requirement to allocate many full-size buffers for
every frame. The first adapters may still encapsulate legacy preset access, but
new generic operations must use the explicit contract.

### Neck dissolve as the first proof

The reusable primitive is a directional falloff region with origin, angle,
start, width, curve and strength. It can be attached to any object's local frame
or to the canvas. Begin with the linear/smoothstep falloff needed here; radial
and noisy variants can follow when a study actually needs them.

The current profile recipe binds this region to three operations:

1. Attenuate the contour before glow, shifted fringe and echo are generated.
2. Blend the backlight field with its softened version before applying grain.
3. Attenuate the body fill in the same region.

This order matters. Applying an opacity gradient to the finished frame would
also dim the background and leave a different contour/glow result.

The model adapter supplies the matching projected coordinate frame. The profile
recipe supplies the current start (`.9`), width (`.38`), smoothstep curve and
backlight blur scale (`.065` of reference width). Generic region code knows
nothing about a head, a jaw or the `silhouette` module ID.

“Neck dissolve” can remain the profile starter's convenient macro. Its underlying
region can be exposed under Advanced as a general directional fade, reusable at
the bottom of a square, along a logo edge or across an imported stamp. Preserve
the full response of the existing strength control, including zero and partial
strength, rather than only matching its current value of one.

## Compatibility contract

Freeze the nine starters currently registered in `synth_starters.py`: Refined
signal, Approved signal, Particle head, Expand / orbit, Original particles,
Ink bloom, Profile / phosphor scan, Profile / signal echoes and Mixed media /
two bursts.

Each frozen revision needs fully resolved parameter data, asset identities,
seeds, timing and renderer/default-set versions. A document schema version only
describes storage; it does not identify the algorithm that produces the pixels.

- Start with a versioned legacy compiler/render path that preserves current
  normalization, defaults and evaluation behavior. Merely tagging a mutable
  renderer as version one is insufficient.
- Existing documents open through that compatibility path. Resolve unversioned
  documents using the baseline behavior, without overwriting the original.
  Historical behavior already changed before this baseline cannot be recovered
  from missing version information alone; retain the corresponding old app/tag
  where that is required.
- Port treatments individually. If a port cannot reproduce a starter yet, that
  starter continues using its compatible renderer.
- New recipe revisions can use new operations. Offer upgrades as separate
  editable copies; keep the original recipe available and unchanged.
- Give new effect instances stable IDs and explicit algorithm versions. Preserve
  the old seed derivation in compatibility adapters; do not inadvertently
  reseed existing effects when adding instance IDs.
- Keep whole-clip and section override precedence, duration accumulation,
  shared timing, locks, variation, save/load and undo behavior intact.

Exact frame comparisons apply to raw pixels in a pinned rendering environment.
Record dependency versions and asset hashes as part of the baseline. Lossy MP4
encoding and future platform/backend changes need appropriate visual comparison;
do not substitute compressed-video hashes for renderer regression tests.

## Migration in reviewable steps

### 1. Freeze the current output

Capture resolved starter fixtures and baseline renders before changing code.
Cover every frame at an economical validation resolution, and representative
frames at working/full resolutions. Include all supported canvas presets,
artistic low-resolution settings, section boundaries, and the latest neck blend.
Retain a small visual review sheet/video for each starter outside source control;
commit compact fixtures, manifests and expected raw-frame hashes.

Exit: a deliberate visual change is detected; unchanged baseline output passes.

### 2. Add the contract and compatibility adapters

Add render context, source outputs and explicit region bindings alongside the
existing renderer. Keep legacy evaluation as the default for existing documents.
Introduce version dispatch and freeze defaults before new defaults can affect
old recipes. Preserve current source combinations and canvas policies.

Exit: all baseline checks pass, including document round trips, preview/export
agreement at equivalent settings and out-of-order scrubbing. Measure warm render
latency and memory at the existing preview sizes; investigate material overhead
before proceeding.

### 3. Extract the directional region and port the neck treatment

Move source-coordinate knowledge into the source adapter and artistic placement
into the recipe. Add the reusable region and bind it to the existing phosphor
contributions at their original evaluation stages. Keep the recognizable profile
macro and add advanced region controls in context.

Exit: unchanged profile output at zero, partial and full dissolve; unchanged face
detail outside the region; correct behavior after object translation, rotation,
scale and canvas changes. Demonstrate the same primitive on a geometric shape
and imported artwork without source-ID branches. Other starters still pass.

### 4. Extract the next shared treatments

Decouple slab ghosts and halo next, one family per change. Expose the smallest
useful contributions instead of forcing an immediate split of every renderer.
Represent compound effects as recipes over operations, retaining their current
effect inspector where useful. Each extraction must work on another source and
pass its legacy visual checks before replacing a compatibility implementation.

### 5. Make recipes and controls independent

Store starter revisions as explicit recipe data with macro bindings, rather than
relying on changing global defaults. Use stable effect/parameter IDs for future
automation. Present source-specific controls under Object and applicable
treatments under Effects, retaining the applied/available distinction. Show
which contribution and region a treatment affects. Explain missing capabilities
instead of offering controls that silently do nothing.

Keep a simple artistic view; Advanced reveals region and operation parameters.
Replacing an object preserves compatible treatments, timing and canvas settings.
Recipe macros should display their effective scope and values across sections.

## First implementation milestone

Steps 1–3 form the initial milestone: protected starters plus one proven reusable
region, demonstrated on a head, a shape and custom artwork. This validates the
architecture against the concrete problem before widening the refactor.

A node editor, arbitrary effect reordering, compositing layers, GPU rewrite,
general automation editor and video-source integration are separate milestones.
Stable instances and explicit inputs leave room for them, but none is required
to make the present effects reusable or preserve the current work.
