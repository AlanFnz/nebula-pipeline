# Visual Study browser

Status: ready for implementation in parallel with editing/preview improvements.
Prepared: 2026-09-30.
Baseline: 167636b plus playback-icons commit dee20f4 (PR #8).

## Outcome

Let the user recognize, find and revisit Studies visually while keeping the
compact Studies picker in the main toolbar. Evolve the existing Manage studies
dialog into a browser with thumbnails, a larger selected-item preview, search,
category filters and favorites. Preserve dates, multi-selection, reversible
removal, restoration, independent snapshots and all source-media paths.

This is a library/discovery feature. Layering, effect presets, new rendering
algorithms and timeline editing are separate work.

## User experience

- Keep the compact picker and Load study action. Rename Manage to Browse studies
  when integration is ready; opening the browser does not load a composition.
- Use a thumbnail list/table with name, date, category, built-in/saved origin and
  an accessible favorite toggle. Retain date/name sorting and multi-selection.
- Show a larger still, name, origin, category and date for one selected Study.
  A single click inspects it. Load and double-click request a fresh editable copy.
- Search names case-insensitively. Combine search with category, Favorites only
  and the existing Removed studies filter. Provide a clear empty-results state.
- Categories: Signals, Profiles, Particles, Mixed media, Text, Video, Other.
  Explicit built-in mappings are preferable to guessing from display labels.
  Classify saved recipes from actual source capabilities; unknown content is Other.
- Favorites are library preferences and do not modify artistic documents. A
  removed favorite keeps its favorite status when restored. Duplicate names
  remain independent through stable IDs.
- Keep Remove selected / Restore selected reversible and preserve the existing
  multi-selection behavior. Removed entries cannot load until restored.
- Missing footage or a thumbnail error displays an informative placeholder;
  one broken item cannot prevent browsing, favorites, removal or restoration.
- Keep the terminal colors and current typography. No autoplaying animated
  thumbnails or constantly running preview while browsing.

## Persistence and compatibility

Files: `synth_studies.py`, `synth_studies_ui.py`, an isolated thumbnail helper,
and focused library/browser tests. The root agent owns README/CHANGELOG and
integration into `synth_studio.py`; do not edit that window from this task.

- Extend the library index compatibly with optional favorites data. Existing
  schema-1 removed-only files must load with an empty favorites set.
- All preference writes are atomic and preserve the other preference fields.
  Removal must never drop favorites, and favoriting must never unhide entries.
- Preserve the strict corrupt-index behavior: read-only browsing can recover,
  but mutation must not silently overwrite a malformed index.
- Preserve dates and stable personal IDs through library moves. Do not write
  into built-in assets, mutate study JSON, relocate media or embed thumbnails
  in composition documents. Existing Study labels/picker ordering may remain.
- Derive category metadata without rendering. Cache repeated expensive metadata
  inspection within a dialog refresh where useful; avoid repeated compiles.

## Thumbnail generation

- Render through the existing compiler/renderer at a small resolution and the
  Study's original aspect ratio. Letterbox within thumbnail/preview frames;
  never stretch the image or reinterpret the user's canvas settings.
- Pick a deterministic representative time (roughly one-third of duration).
  If a sample is nearly blank, permit at most one deterministic fallback sample.
  This is a still preview, not a summary animation.
- Generate asynchronously with one bounded worker/queue per browser. Prioritize
  the selected entry and visible rows. Avoid scheduling the entire library at
  dialog creation or generating full-resolution frames for thumbnails.
- Each worker owns its video frame provider. GUI work stays on the GUI thread;
  communicate image bytes/QImage safely and create QPixmap in that thread.
- Cancel obsolete work on refresh/filter/close and reject late callbacks by
  generation and stable ID. Opening, searching and closing remain responsive.
- Browser work has lower priority than active editing/export; stop background
  thumbnail warming while the dialog is hidden. Bound pending frame deliveries.
- Cache thumbnails outside the recipe/library media, under the app's cache
  location. Key by recipe content, rendering version, output size, source and
  asset identity. A changed/relinked source or edited saved recipe invalidates
  its cached image. Include library location where necessary to avoid collisions.
- Bound memory/disk cache size. Handle an unwritable cache by showing the
  generated result without persistence; cache failures must not block the library.
- No regenerating approved baseline fixtures and no changing renderer defaults.

## Main-window integration contract

Expose `studyRequested = Signal(str)` from StudiesDialog. Emit it from Load or
successful double-click of one available Study. Root connects it to the same
user-facing guarded load path as the compact picker in the editing task.

The dialog must remain open and the current composition remain intact if the
user cancels replacement. Resolve the Study at load time so removal/changed
files cannot silently load a stale cached document. Keep `libraryChanged`
for picker refresh. Report any additional integration hooks needed to root.

## Validation

- Existing save/load, removal/restore, media relocation and corrupt-index tests.
- Combined filters, sorting, favorites persistence, duplicate names, reversible
  removal, unchanged dates and zero mutation of source recipes/media.
- Native Qt interaction for selection, accessible star toggles, Load vs inspect,
  empty results, broken video and loading through the unsaved-change guard.
- Thumbnail aspect ratio, cache hits/invalidation, missing source, write failure,
  queue bounds and stale result rejection on refresh/close. Inject a small
  deterministic renderer for queue tests; retain representative real renders.
- Compare representative generated and video thumbnail samples with the existing
  renderer. Confirm app opening does not eagerly render all Studies.
- Report measured dialog/search responsiveness with a representative library;
  do not claim performance targets without measurements.

## Delivery

Implement in separate commits for metadata/favorites and browser/thumbnails,
with a later root integration commit. Agents do not commit, push, switch branch,
build/restart the app or edit shared documentation while running in parallel;
root owns those steps after reviewing completed changes.

Keep the visual browser independent of the current-document preview cache. Its
bounded thumbnail queue should not require renderer changes or the scheduler
from the other agent. Notify root when the signal contract is ready.
