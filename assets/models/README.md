# Human head sampling mesh

`human-head.npz` is a head-and-neck extract of MakeHuman's base mesh, by the
MakeHuman Team. It is bundled under **CC0 1.0 Universal**; the accompanying
`LICENSE.CC0.txt` is the upstream asset license. No MakeHuman application code
is included.

- Source commit: `a8bc2d54ff0ac92e78ff71431b1023eda42bf482`
- [Original asset](https://github.com/makehumancommunity/makehuman/blob/a8bc2d54ff0ac92e78ff71431b1023eda42bf482/makehuman/data/3dobjs/base.obj)
- [Asset licensing statement](https://github.com/makehumancommunity/makehuman/blob/a8bc2d54ff0ac92e78ff71431b1023eda42bf482/LICENSE.md)
- Original OBJ SHA-256: `8e761e6624b8f54536409135d1636da63b32486a90d4897f84e121d144f6fb4c`

Only the `body` faces entirely above Y=5.85 are retained, triangulated, centered
at (0, 7.3, 0.45), and uniformly scaled by 0.86. Vertex normals are averaged
from adjacent face normals. No facial geometry is procedurally exaggerated.
The result contains 4,286 vertices and 8,524 triangles.

`portrait-head.npz` is a separate refinement of the same pinned CC0 asset. It
also retains `helper-l-eye` and `helper-r-eye` surfaces and applies one
Catmull–Clark subdivision pass, preserving open boundary loops. The same centering
and uniform scale are used, with vertex normals recomputed afterward. It contains
17,659 vertices and 35,216 triangles. The original `human-head.npz` is unchanged.

To rebuild from the pinned source OBJ:

```sh
.venv/bin/python scripts/build_head_asset.py /path/to/base.obj assets/models/human-head.npz
.venv/bin/python scripts/build_head_asset.py /path/to/base.obj assets/models/portrait-head.npz --portrait
```

The renderer samples triangles by surface area with stable seeded barycentric
coordinates. The surface is never drawn; it only guides particle positions and
their lighting. Portrait particles receive a subdued iris brightness mask;
optional point-depth occlusion prevents internal mouth and far-side points from
shining through the assembled face. Mesh import through the UI is not yet supported.
