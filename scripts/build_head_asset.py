#!/usr/bin/env python3
"""Extract MakeHuman's CC0 head/neck mesh from a local, pinned base.obj.

Only asset data is read; no MakeHuman application code is used or bundled.
Source and license are recorded in assets/models/README.md.
"""
import argparse
import hashlib
from pathlib import Path

import numpy as np


def subdivide(vertices, polygons):
    """One Catmull–Clark pass, with preserved open boundary loops."""
    centers = np.array([vertices[face].mean(axis=0) for face in polygons])
    edges, vertex_faces, vertex_edges = {}, [[] for _ in vertices], [[] for _ in vertices]
    for face_id, face in enumerate(polygons):
        for i, vertex in enumerate(face):
            vertex_faces[vertex].append(face_id)
            edge = tuple(sorted((vertex, face[(i + 1) % len(face)])))
            edges.setdefault(edge, []).append(face_id)
    edge_ids = {}
    edge_points = []
    for edge, faces in edges.items():
        edge_ids[edge] = len(vertices) + len(edge_points)
        midpoint = vertices[list(edge)].mean(axis=0)
        edge_points.append((midpoint * 2 + centers[faces].sum(axis=0)) / 4 if len(faces) == 2 else midpoint)
        for v in edge:
            vertex_edges[v].append(edge)
    smoothed = vertices.copy()
    for v, connected in enumerate(vertex_edges):
        boundary = [edge[1] if edge[0] == v else edge[0] for edge in connected if len(edges[edge]) == 1]
        if len(boundary) == 2:
            smoothed[v] = vertices[v] * .75 + vertices[boundary].sum(axis=0) * .125
        elif connected and not boundary:
            n = len(connected)
            midpoints = np.array([vertices[list(edge)].mean(axis=0) for edge in connected])
            smoothed[v] = (centers[vertex_faces[v]].mean(axis=0) + 2 * midpoints.mean(axis=0) + (n - 3) * vertices[v]) / n
    faces_out = []
    for f, face in enumerate(polygons):
        center_id = len(vertices) + len(edges) + f
        for i, v in enumerate(face):
            after = edge_ids[tuple(sorted((v, face[(i + 1) % len(face)])))]
            before = edge_ids[tuple(sorted((face[i - 1], v)))]
            faces_out.append((v, after, center_id, before))
    return np.concatenate((smoothed, edge_points, centers)), faces_out


def extract(source, destination, portrait=False):
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
        elif fields[0] == "f" and (group == "body" or portrait and group in {"helper-l-eye", "helper-r-eye"}):
            polygons.append([int(value.split("/")[0]) - 1 for value in fields[1:]])
    vertices = np.asarray(vertices, dtype=np.float64)
    if portrait:
        polygons = [face for face in polygons if np.min(vertices[face, 1]) >= 5.85]
        used = np.unique([index for face in polygons for index in face])
        lookup = {v: i for i, v in enumerate(used)}
        vertices = vertices[used]
        polygons = [[lookup[v] for v in face] for face in polygons]
        vertices, polygons = subdivide(vertices, polygons)
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
    parser.add_argument("--portrait", action="store_true", help="Include eye surfaces and smooth the head with one subdivision pass")
    args = parser.parse_args()
    extract(args.source, args.destination, args.portrait)
