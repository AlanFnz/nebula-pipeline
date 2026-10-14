"""Portable static glTF geometry. Files are read only at explicit import time."""
from __future__ import annotations

import base64
import binascii
from functools import lru_cache
from io import BytesIO
import json
import math
from pathlib import Path
import struct
from urllib.parse import unquote, urlsplit
import zipfile

import numpy as np

PREFIX = 'data:application/x-nebula-mesh;base64,'
MAX_FILE = 64_000_000
MAX_PACKED = 16_000_000
MAX_RAW = 24_000_000
MAX_FACES = 60_000
MAX_VERTICES = 180_000


def _arrays(vertices, normals, faces):
    v,n,f = np.asarray(vertices),np.asarray(normals),np.asarray(faces)
    if v.ndim != 2 or v.shape[1:] != (3,) or not 3 <= len(v) <= MAX_VERTICES:
        raise ValueError('Use a model with at most 180,000 vertices.')
    if n.shape != v.shape or not np.isfinite(v).all() or not np.isfinite(n).all():
        raise ValueError('The model contains invalid positions or normals.')
    if f.ndim != 2 or f.shape[1:] != (3,) or not 1 <= len(f) <= MAX_FACES or f.dtype.kind not in 'iu':
        raise ValueError('Use a static model with at most 60,000 triangles.')
    if f.min() < 0 or f.max() >= len(v): raise ValueError('The model contains invalid triangle indices.')
    if np.max(np.abs(v)) > .501: raise ValueError('Embedded model positions must be centered and normalized.')
    lengths=np.linalg.norm(n,axis=1)
    if np.any(lengths < .5) or np.any(lengths > 1.5): raise ValueError('The model has invalid surface normals.')
    return v.astype(np.float32),n.astype(np.float32),f.astype(np.int32)


def encode_mesh(vertices, normals, faces, name):
    v=np.asarray(vertices,dtype=np.float64)
    if v.ndim!=2 or v.shape[1:]!=(3,) or not len(v) or not np.isfinite(v).all():
        raise ValueError('No usable mesh geometry was found.')
    extent=np.ptp(v,axis=0).max()
    if extent < 1e-12: raise ValueError('The model has no visible size.')
    v=(v-(v.min(axis=0)+v.max(axis=0))*.5)/extent
    v,n,f=_arrays(v,normals,faces)
    info=np.frombuffer(json.dumps({'name':str(name)[:120],'version':1}).encode(),dtype=np.uint8)
    buf=BytesIO();np.savez_compressed(buf,vertices=v,normals=n,faces=f,info=info)
    value=PREFIX+base64.b64encode(buf.getvalue()).decode('ascii')
    validate_mesh(value)
    return value


@lru_cache(maxsize=8)
def decode_mesh(value):
    if not isinstance(value,str) or not value.startswith(PREFIX) or len(value)>MAX_PACKED:
        raise ValueError('Use an embedded Nebula model imported from GLB or glTF.')
    try:
        raw=base64.b64decode(value[len(PREFIX):],validate=True)
        with zipfile.ZipFile(BytesIO(raw)) as archive:
            if set(archive.namelist()) != {'vertices.npy','normals.npy','faces.npy','info.npy'} or len(archive.infolist()) != 4:
                raise ValueError('Invalid embedded model archive.')
            if sum(i.file_size for i in archive.infolist()) > MAX_RAW:
                raise ValueError('The embedded model is too large.')
            # Check .npy headers before NumPy can allocate from their shapes.
            for member in archive.infolist():
                with archive.open(member) as source:
                    version=np.lib.format.read_magic(source)
                    if version not in ((1,0),(2,0)): raise ValueError('Unsupported array encoding.')
                    reader=np.lib.format.read_array_header_1_0 if version==(1,0) else np.lib.format.read_array_header_2_0
                    shape,_,dtype=reader(source)
                    if dtype.hasobject or dtype.kind not in 'fiu' or len(shape)>2 or any(d<0 for d in shape):
                        raise ValueError('Invalid model array.')
                    size=math.prod(shape)*dtype.itemsize
                    if size>MAX_RAW or size!=member.file_size-source.tell(): raise ValueError('Invalid model array size.')
        with np.load(BytesIO(raw),allow_pickle=False) as data:
            v,n,f=_arrays(data['vertices'],data['normals'],data['faces'])
            info=data['info']
            if info.dtype!=np.uint8 or info.ndim!=1 or len(info)>2048: raise ValueError('Invalid model information.')
            meta=json.loads(info.tobytes())
            if meta.get('version')!=1 or not isinstance(meta.get('name'),str) or len(meta['name'])>120:
                raise ValueError('Unsupported embedded model version.')
        for a in (v,n,f): a.setflags(write=False)
        return v,n,f,meta['name']
    except (OSError,ValueError,KeyError,TypeError,UnicodeError,EOFError,zipfile.BadZipFile,binascii.Error) as exc:
        raise ValueError('Cannot read the embedded model: '+str(exc)) from exc


def validate_mesh(value):
    if not isinstance(value, str): raise ValueError('The embedded model must be text.')
    if value=='': return value
    decode_mesh(value)
    return value


def _read_document(path):
    if path.suffix.lower() not in ('.glb','.gltf'): raise ValueError('Choose a GLB or glTF 2.0 file.')
    if path.stat().st_size>MAX_FILE: raise ValueError('Use a model file smaller than 64 MB.')
    raw=path.read_bytes()
    if path.suffix.lower()=='.glb':
        if len(raw)<20 or raw[:4]!=b'glTF': raise ValueError('Invalid GLB file.')
        _,version,length=struct.unpack_from('<III',raw)
        count,kind=struct.unpack_from('<II',raw,12)
        if version!=2 or length!=len(raw) or kind!=0x4e4f534a or 20+count>len(raw):
            raise ValueError('Choose a valid GLB 2.0 file.')
        doc=json.loads(raw[20:20+count])
    else: doc=json.loads(raw)
    if doc.get('asset',{}).get('version')!='2.0': raise ValueError('Only glTF 2.0 is supported.')
    if doc.get('skins') or any(p.get('targets') for m in doc.get('meshes',[]) for p in m.get('primitives',[])):
        raise ValueError('Export a static mesh with skinning and morph targets baked before importing.')
    if any('compression' in e.lower() or 'meshopt' in e.lower() for e in doc.get('extensionsUsed',[])):
        raise ValueError('Export an uncompressed GLB/glTF (without Draco or meshopt compression).')
    if len(doc.get('nodes',[]))>4096 or any(a.get('count',0)>MAX_VERTICES*3 for a in doc.get('accessors',[])):
        raise ValueError('The model is too complex. Export a simplified static mesh.')
    resources={};total=len(raw)
    for buffer in doc.get('buffers',[]):
        if buffer.get('byteLength',0)>MAX_FILE: raise ValueError('The model buffer is too large.')
        uri=buffer.get('uri','')
        if not uri or uri.startswith('data:'): continue
        parsed=urlsplit(uri)
        target=(path.parent/unquote(parsed.path)).resolve()
        if parsed.scheme or parsed.netloc or not target.is_relative_to(path.parent.resolve()):
            raise ValueError('Keep glTF buffers in the model folder. Remote and outside-folder assets are unsupported.')
        total+=target.stat().st_size
        if total>MAX_FILE: raise ValueError('Use a model and buffers totaling less than 64 MB.')
        resources[uri]=target.read_bytes()
    return raw,resources


def import_mesh(path):
    """Flatten the scene's static node transforms, embed geometry, discard paths.

    Materials/textures are intentionally skipped: the studio supplies white
    plastic or optical color. No remote resources are fetched by this loader.
    """
    import trimesh
    path=Path(path).resolve()
    try:
        raw,resources=_read_document(path)
        scene=trimesh.load_scene(BytesIO(raw),file_type=path.suffix[1:].lower(),resolver=resources,
                                 process=False,skip_materials=True,allow_remote=False)
        vertices=[];normals=[];faces=[];offset=0;face_count=0
        for node in scene.graph.nodes_geometry:
            matrix,key=scene.graph[node];mesh=scene.geometry[key]
            if not isinstance(mesh,trimesh.Trimesh) or not len(mesh.faces): continue
            offset_next=offset+len(mesh.vertices);face_count+=len(mesh.faces)
            if offset_next>MAX_VERTICES or face_count>MAX_FACES:
                raise ValueError('Simplify the model to at most 60,000 triangles / 180,000 vertices.')
            linear=matrix[:3,:3]
            if abs(np.linalg.det(linear))<1e-12: raise ValueError('The model has a collapsed node transform.')
            v=np.asarray(mesh.vertices)@linear.T+matrix[:3,3]
            # glTF authored normals are cached by trimesh. Generate missing ones
            # locally without depending on its optional scipy sparse backend.
            local_normals=mesh._cache['vertex_normals']
            if local_normals is None:
                local_normals=np.zeros_like(mesh.vertices)
                triangles=np.asarray(mesh.vertices)[mesh.faces]
                weighted=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
                for corner in range(3): np.add.at(local_normals,mesh.faces[:,corner],weighted)
            n=np.asarray(local_normals)@np.linalg.inv(linear)
            lengths=np.linalg.norm(n,axis=1,keepdims=True)
            n=n/np.maximum(lengths,1e-12)
            # Isolated vertices are harmless but need a defined normal.
            n[lengths[:,0]<1e-12]=(0,1,0)
            f=np.asarray(mesh.faces,dtype=np.int32).copy()
            if np.linalg.det(linear)<0: f=f[:,::-1]
            vertices.append(v);normals.append(n);faces.append(f+offset);offset=offset_next
        if not vertices: raise ValueError('No triangle meshes were found in this file.')
        return encode_mesh(np.concatenate(vertices),np.concatenate(normals),np.concatenate(faces),path.stem)
    except (OSError,ValueError,KeyError,IndexError,TypeError,NotImplementedError,struct.error) as exc:
        raise ValueError('Cannot import model: '+str(exc)) from exc
