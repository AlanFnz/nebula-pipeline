"""Bundled head geometry shared by particle sampling and solid silhouettes."""
from functools import lru_cache
from pathlib import Path

import numpy as np


HEAD_MODELS = ('portrait-head', 'human-head', 'doryphoros-head')


@lru_cache(maxsize=3)
def head_mesh(model):
    if model not in HEAD_MODELS:
        raise ValueError(f'Unknown head model: {model}')
    path = Path(__file__).parent / "assets" / "models" / (model + '.npz')
    with np.load(path, allow_pickle=False) as data:
        vertices, faces, normals = data["vertices"], data["faces"], data["normals"]
    triangles = vertices[faces].astype(np.float64)
    vertex_normals = normals[faces].astype(np.float64)
    area = np.linalg.norm(np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]), axis=1)
    cumulative = np.cumsum(area / area.sum())
    cumulative[-1] = 1.
    for array in (triangles, vertex_normals, cumulative):
        array.setflags(write=False)
    return triangles, vertex_normals, cumulative


def _head_mesh(portrait=False):
    """Compatibility entry point for the original two assets."""
    return head_mesh('portrait-head' if portrait else 'human-head')


def sample_human_head(random, portrait=False):
    return sample_head(random, 'portrait-head' if portrait else 'human-head')


def sample_head(random, model):
    triangles, vertex_normals, cumulative = head_mesh(model)
    index = np.searchsorted(cumulative, random[:, 0])
    root = np.sqrt(random[:, 1])
    barycentric = np.column_stack((1 - root, root * (1 - random[:, 2]), root * random[:, 2]))
    points = (triangles[index] * barycentric[:, :, None]).sum(axis=1)
    normals = (vertex_normals[index] * barycentric[:, :, None]).sum(axis=1)
    normals /= np.maximum(1e-12, np.linalg.norm(normals, axis=1, keepdims=True))
    return points, normals
