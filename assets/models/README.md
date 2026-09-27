# Bundled head meshes

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
coordinates. The particle renderer uses the surface only to guide particle positions and
their lighting. The separate Model silhouette source projects the same bundled
triangles into a solid mask, with a fixed editable pose and optional neck
extension; it does not change either mesh asset. Portrait particles receive a subdued iris brightness mask;
optional point-depth occlusion prevents internal mouth and far-side points from
shining through the assembled face. Mesh import through the UI is not yet supported.

## Doryphoros

`doryphoros-head.npz` is derived from **The head of “Doryphoros” – a plaster cast**,
inventory **Rz 7**, Museum of the Academy of Fine Arts in Kraków. Digitisation:
Regional Digitalisation Lab, Małopolska Institute of Culture (MIK), Virtual
Małopolska project. The publisher releases the scan under **CC0 1.0 Universal**
(the license text is also included in `LICENSE.CC0.txt`).

- [Publisher and license](https://sketchfab.com/3d-models/the-head-of-doryphoros-a-plaster-cast-59c2a8477e0945d7817b61d5088a97fd)
- [Museum catalogue](https://muzea.malopolska.pl/en/objects-list/2270)
- [Public archive, DOI 10.5281/zenodo.21530396](https://zenodo.org/records/21530396),
  sourced from Objaverse 1.0 / Sketchfab with the same model identifier.
- [Original GLB](https://zenodo.org/records/21530396/files/59c2a8477e0945d7817b61d5088a97fd.glb?download=1)
- Original GLB SHA-256: `48e257f61de8b4ed1402627b8b610e6cf99d0fbc7d5010c15953e642f5a10590`

The preparation script reads only the three mesh primitives from this pinned
GLB. It welds duplicate vertices at texture seams, simplifies 252,368 triangles
to 32,000 with `fast-simplification==0.1.13`, aligns the face to +Z and up to +Y,
and centers/uniformly scales the head to the existing source coordinate system.
The bundled result contains 16,002 vertices. Vertex normals are recomputed;
textures, materials and lighting are not bundled. The facial proportions are
not procedurally exaggerated. The silhouette source can still apply its optional
pose, facial definition and neck controls at render time.

To rebuild (the simplifier is a **build-only** dependency):

```sh
.venv/bin/python -m pip install fast-simplification==0.1.13
.venv/bin/python scripts/build_doryphoros_asset.py /path/to/59c2a8477e0945d7817b61d5088a97fd.glb assets/models/doryphoros-head.npz
```

The model is available as **Object → Head model → Doryphoros** for silhouettes
and **Object → Attractor → Doryphoros** for particles. The separate
**Profile / Doryphoros · 8s** starter uses the existing phosphor/scan choreography
with facial definition and neck fullness at zero. Both MakeHuman assets and all
previous model IDs, default settings and starter recipes remain unchanged.
