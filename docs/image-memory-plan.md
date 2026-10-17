# Memory / afterimage garden

## Intent

Create a 15-second original study in Nebula's analog vocabulary. A luminous
object draws a changing landscape with its previous positions. Recent traces
retain its silhouette; older traces drift, change color and dissolve. Motion
should accelerate and settle smoothly, with no mechanical sequence of cuts.

## Controls and interaction

- **Persistence** (seconds): the visible history window; zero leaves the object.
- **Drift**: how far deposited traces travel independently of the object.
- **Dissolution**: progressive loss of contour and body in older traces.
- Secondary controls: trail opacity, expansion and drift direction; sphere,
  ring or polygon; size and polygon sides; orbit, figure eight or wandering
  path; travel, motion period, motion variation, phase and rotation; palette,
  color evolution, light, optical softness and glow.
- Put the three main controls first in the Object inspector. Keep the complete
  source controls grouped by memory, shape, motion, color and finish. Hide
  polygon sides when irrelevant. Existing project/clip scope, undo, reset,
  saving and snapshots own edits.

## Rendering contract

1. Add an opt-in `image_memory` procedural source, appended to the module list
   so legacy indices and random seeds do not change. Replacing the object uses
   the existing Object selector. This milestone traces its own generated form;
   it does not claim arbitrary video/3D temporal feedback support.
2. Evaluate past object poses analytically from absolute source time with a
   bounded history. Use continuous easing, deterministic spatial erosion and
   age-based decay. No persistent framebuffer, dependence on playback order,
   unbounded caches or history rendering of other effects.
3. Use a bounded sample count and rasterize each trace only in its local bounds.
   Distances use the artwork frame uniformly, preserving shapes when reframed.
   History starts with the piece and builds gradually, with smooth births and
   deaths of traces. Preview and export use the same algorithm.
4. Apply the existing Color emulsion and CRT treatments after the generated
   image. Their controls, including Intensity, remain independently editable.
   No changes to their algorithms, defaults or existing study files.
5. Ship a portable frozen study recipe without external assets. Document the
   controls, temporal behavior and the initial source limitation honestly.

## Delivery and validation

1. Capture existing study frame hashes, implement the source and inspect stills
   and a motion preview; tune composition and movement before freezing a recipe.
2. Integrate Object selection, treatment anchors, source metadata, study library
   and parameter units; verify edits, undo, scope and save/reopen in the UI.
3. Test zero history, zero drift/dissolution, shape extremes, deterministic seek,
   finite bounded output, resizing/reframing and existing pixel baselines.
   Render a complete MP4 preview and inspect representative frames and movement.
4. Update README/changelog and version, commit in reviewable units, merge and
   install under the user's standing authorization. Open the new study while
   preserving any unsaved current composition.

## Implemented result and validation

The starting shape is a luminous ring, with a 9-second memory and a 6.4-second
wandering motion period. Overlapping traces travel from amber through coral
into turquoise. The 15-second study uses a 720×960 canvas at 24 fps. Sphere and
polygon remain selectable; the three main controls precede placement controls
in Object. Full settings are available in the source inspector.

- 30 new source, persistence, scope, UI and export tests passed.
- 184 existing renderer/source/study/intensity tests and 18 UI regressions passed.
- 58 previously captured study frames remain byte-identical.
- Narrow-inspector layout inspected at 1280×800; focused layout test rerun.
- Full 360-frame MP4 exported and decoded; sampled full-resolution output agrees
  with preview within H.264 compression error (mean channel error 2.35 / 255).
- macOS bundle built successfully and verified by the packaging signature check.
