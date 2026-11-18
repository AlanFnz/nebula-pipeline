# Repository organization

[Development guide](development.md)

The November 2026 review found 211 tracked Python files at the repository root,
including 194 `synth*` modules. A static import inventory found no unreferenced
application module suitable for deletion: the three files without importers
were executable entry points (`generate.py`, `mac_app.py` and `nebula.py`).
This inventory is evidence for keeping those modules, not proof that every
function or asset is still needed.

The application now lives in `nebula/`, split into `ui`, `documents`, `sources`,
`effects`, `render`, `audio`, `core` and `legacy`. Nine Python files remain at the
root: the existing launch commands and canonical version metadata. Scripts,
tests, documentation, assets, presets and packaging keep their own directories.

This is a structural change. The renderer calculations, source/effect IDs,
project schemas, study recipes and bundled assets are preserved. Imports and
resource lookup paths are updated together. The earlier terminal pipeline and
render-version compatibility modules remain because they are still entry
points or dependencies. No personal projects, media or caches are deleted.

The packages organize responsibility; they do not yet establish strict one-way
dependency layers. Future work can split large controllers when a concrete
change requires it, rather than combining that behavior refactor with a move.
Preserve the `synth_*` basenames for now to make history and existing development
notes easier to follow.

Validation includes test collection, the existing behavior and frozen-render
suites, command-line entry points and a frozen macOS build. Resource lookup and
package imports are also checked independently of the working directory.
