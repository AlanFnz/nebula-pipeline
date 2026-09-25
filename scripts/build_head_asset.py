#!/usr/bin/env python3
"""Extract MakeHuman's CC0 head/neck mesh from a local, pinned base.obj.

Only asset data is read; no MakeHuman application code is used or bundled.
Source and license are recorded in assets/models/README.md.
"""
import argparse
import hashlib
from pathlib import Path

import numpy as np


def extract(source, destination):
    if hashlib.sha256(Path(source).read_bytes()).hexdigest() != "8e761e6624b8f54536409135d1636da63b32486a90d4897f84e121d144f6fb4c":
        raise ValueError("Use the pinned MakeHuman base.obj listed in assets/models/README.md")
    vertices, polygons = [], []
    group = ""
    for line in Path(source).read_text().splitlines():
        fields = line.split()
        if not fields:
            continue
        if fields[0] == "v":
            vertices.append([float(value) for value in fields[1:4]])
        elif fields[0] == "g":
            group = " ".join(fields[1:])
        elif fields[0] == "f" and group == "body":
            polygons.append([int(value.split("/")[0]) - 1 for value in fields[1:]])
    vertices = np.asarray(vertices, dtype=np.float64)
    triangles = []
    for polygon in polygons:
        if np.min(vertices[polygon, 1]) < 5.85:
            continue
        triangles.extend((polygon[0], polygon[index], polygon[index + 1]) for index in range(1, len(polygon) - 1))
    used, inverse = np.unique(triangles, return_inverse=True)
    faces = inverse.reshape(-1, 3)
    vertices = (vertices[used] - np.array((0., 7.3, .45))) * .86
    normals = np.zeros_like(vertices)
    corners = vertices[faces]
    face_normals = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    for corner in range(3):
        np.add.at(normals, faces[:, corner], face_normals)
    normals /= np.maximum(1e-12, np.linalg.norm(normals, axis=1, keepdims=True))
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(destination, vertices=vertices.astype("float32"), faces=faces.astype("int32"), normals=normals.astype("float32"))
    print(f"{destination}: {len(vertices)} vertices / {len(faces)} triangles")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    extract(args.source, args.destination)
