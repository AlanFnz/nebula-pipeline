#!/usr/bin/env python3
"""Prepare the pinned CC0 Doryphoros scan for silhouette and particle sources.

Build-only dependency: fast-simplification==0.1.13. The app needs only the NPZ.
This is deliberately an extractor for one verified asset, not a GLB importer.
See assets/models/README.md for provenance and the original download.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

import numpy as np


SOURCE_SHA256 = "48e257f61de8b4ed1402627b8b610e6cf99d0fbc7d5010c15953e642f5a10590"


def read_scan(path):
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != SOURCE_SHA256:
        raise ValueError("Use the original Doryphoros GLB linked in assets/models/README.md")
    length, _ = struct.unpack_from('<II', data, 12)
    document = json.loads(data[20:20 + length])
    binary = data[28 + length:]

    def accessor(index):
        a = document['accessors'][index]
        view = document['bufferViews'][a['bufferView']]
        dtype = {5126: '<f4', 5125: '<u4'}[a['componentType']]
        components = {'SCALAR': 1, 'VEC3': 3}[a['type']]
        return np.frombuffer(binary, dtype=dtype, count=a['count'] * components,
                             offset=view.get('byteOffset', 0) + a.get('byteOffset', 0)).reshape(-1, components)

    vertices, faces, offset = [], [], 0
    for mesh in document['meshes']:
        for primitive in mesh['primitives']:
            v = accessor(primitive['attributes']['POSITION'])
            f = accessor(primitive['indices']).reshape(-1, 3)
            vertices.append(v); faces.append(f + offset); offset += len(v)
    vertices = np.concatenate(vertices).astype(np.float64)
    faces = np.concatenate(faces)
    # Weld the scan's material/UV seams before simplification.
    vertices, inverse = np.unique(vertices, axis=0, return_inverse=True)
    faces = inverse[faces].astype(np.int32)
    return vertices, faces


def prepare(source, destination, triangles=32000):
    import fast_simplification
    vertices, faces = read_scan(source)
    vertices, faces = fast_simplification.simplify(vertices, faces, target_count=triangles, agg=5.)
    # Initial scan alignment; +Y is up and +Z is the face direction.
    vertices = vertices[:, [2, 1, 0]] * (-1, -1, -1)
    center = (vertices.max(0) + vertices.min(0)) / 2
    vertices = (vertices - center) * (2.25 / np.ptp(vertices[:, 1]))
    vertices[:, 1] -= .11
    normals = np.zeros_like(vertices)
    corners = vertices[faces]
    face_normals = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    for corner in range(3):
        np.add.at(normals, faces[:, corner], face_normals)
    normals /= np.maximum(1e-12, np.linalg.norm(normals, axis=1, keepdims=True))
    destination = Path(destination); destination.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(destination, vertices=vertices.astype('float32'), faces=faces.astype('int32'), normals=normals.astype('float32'))
    print(f'{destination}: {len(vertices)} vertices / {len(faces)} triangles')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    prepare(args.source, args.destination)
