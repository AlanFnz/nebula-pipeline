import base64
import copy
from io import BytesIO
import json
import zipfile

import numpy as np
import pytest
import trimesh

from synth import MODULE_BY_ID,default_synth_preset,normalize_synth
from synth_composition import compile_composition,load_composition,save_composition
from synth_effects import normalize_effects
from synth_mesh import PREFIX,decode_mesh,encode_mesh,import_mesh,validate_mesh
from synth_solids import render_solid
from synth_starters import starter_composition
from synth_sequence import render_sequence_frame,_interpolate_presets


def fixture_mesh():
    mesh=trimesh.creation.box(extents=(1.,2.,.5))
    return encode_mesh(mesh.vertices,mesh.vertex_normals,mesh.faces,'Test block')


def params(**changes):
    return {**{s.key:s.default for s in MODULE_BY_ID['solid'].params},'shape':2,'material':1,'model_data':fixture_mesh(),**changes}


@pytest.mark.parametrize('extension',['glb','gltf'])
def test_scene_import_flattens_instances_transforms_and_embeds_geometry(tmp_path,extension):
    mesh=trimesh.creation.box(extents=(1,2,.5))
    scene=trimesh.Scene()
    for offset in (-2,2):
        transform=np.eye(4);transform[0,3]=offset
        transform[0,0]=-1 if offset<0 else 1
        scene.add_geometry(mesh,transform=transform,node_name=str(offset))
    exported=scene.export(file_type=extension)
    if extension=='glb':
        path=tmp_path/'test.glb';path.write_bytes(exported)
    else:
        for name,data in exported.items():(tmp_path/name).write_bytes(data)
        path=tmp_path/'model.gltf'
    value=import_mesh(path)
    v,n,f,name=decode_mesh(value)
    assert len(f)==24
    assert v.min(0)==pytest.approx((-.5,-.2,-.05))
    assert v.max(0)==pytest.approx((.5,.2,.05))
    assert np.linalg.norm(n,axis=1)==pytest.approx(np.ones(len(n)))
    path.unlink()
    assert decode_mesh(value)[3]==name
    assert not v.flags.writeable


@pytest.mark.parametrize('value',[None,{},3,'file:///tmp/test.glb',PREFIX+'oops'])
def test_bad_embedded_assets_fail_in_all_document_paths(value):
    with pytest.raises(ValueError):validate_mesh(value)
    with pytest.raises(ValueError):normalize_effects({'solid':{'params':{'solid.model_data':value}}})
    with pytest.raises(ValueError):normalize_synth({'modules':[{'id':'solid','params':{'model_data':value}}]})


def test_declared_array_bomb_rejected_before_loading():
    header=BytesIO()
    np.lib.format.write_array_header_1_0(header,{'descr':'<f4','fortran_order':False,'shape':(10**10,3)})
    raw=BytesIO()
    with zipfile.ZipFile(raw,'w') as archive:
        for name in ('vertices','normals','faces','info'):archive.writestr(name+'.npy',header.getvalue())
    with pytest.raises(ValueError,match='array size'):decode_mesh(PREFIX+base64.b64encode(raw.getvalue()).decode())


@pytest.mark.parametrize('uri',['../outside.bin','https://example.com/mesh.bin','file:///tmp/mesh.bin'])
def test_import_never_reads_remote_or_outside_folder_buffers(tmp_path,uri):
    path=tmp_path/'model.gltf'
    path.write_text(json.dumps({'asset':{'version':'2.0'},'buffers':[{'uri':uri,'byteLength':4}]}))
    with pytest.raises(ValueError,match='outside-folder'):import_mesh(path)


@pytest.mark.parametrize('extra,match',[
    ({'skins':[{}]},'static mesh'),
    ({'extensionsUsed':['KHR_draco_mesh_compression']},'uncompressed'),
    ({'meshes':[{'primitives':[{'targets':[{}]}]}]},'static mesh'),
])
def test_unsupported_geometry_has_actionable_errors(tmp_path,extra,match):
    path=tmp_path/'model.gltf';path.write_text(json.dumps({'asset':{'version':'2.0'},**extra}))
    with pytest.raises(ValueError,match=match):import_mesh(path)


def test_roundtrip_scope_and_discrete_transition(tmp_path):
    project=starter_composition('color-film-die');before=copy.deepcopy(project['source'])
    project['effects']['solid']={'mode':'on','params':{'solid.shape':2,'solid.model_data':fixture_mesh()}}
    seq=compile_composition(project)
    frame=render_sequence_frame(seq,1.7,(120,180)).tobytes()
    save_composition(tmp_path/'portable.json',project)
    restored=load_composition(tmp_path/'portable.json')
    assert restored['source']==before
    assert render_sequence_frame(compile_composition(restored),1.7,(120,180)).tobytes()==frame
    first=normalize_synth({'modules':[{'id':'solid','params':params()}]})
    second=copy.deepcopy(first)
    next(m for m in second['modules'] if m['id']=='solid')['params']['model_data']=''
    for amount,payload in ((.49,fixture_mesh()),(.5,'')):
        result=_interpolate_presets(first,second,amount)
        assert next(m for m in result['modules'] if m['id']=='solid')['params']['model_data']==payload


def test_depth_buffer_order_independence_and_no_seams():
    v=np.array(((-.4,-.4,-.2),(.4,-.4,-.2),(0,.4,-.2),(-.3,-.3,.2),(.3,-.3,.2),(0,.3,.2)))
    n=np.tile((0.,0.,1.),(6,1));n[:3]=(.8,0,.6)
    faces=np.array(((0,1,2),(3,4,5)))
    values=[encode_mesh(v,n,f,'Layers') for f in (faces,faces[::-1])]
    preset=dict(default_synth_preset(),width=160,height=160)
    arr=np.zeros((160,160,3),np.float32)
    common=dict(yaw=0,pitch=0,roll=0,turn_speed=0,tumble_speed=0,roll_speed=0,scale=.9,shading=1)
    a,b=[render_solid(arr,params(model_data=value,**common),0,preset) for value in values]
    assert np.array_equal(a,b)
    for row in a.max(2)>.01:
        xs=np.flatnonzero(row)
        if len(xs):assert row[xs[0]:xs[-1]+1].all()
    assert np.array_equal(arr,np.zeros_like(arr))


def test_rotation_offset_and_empty_model():
    arr=np.zeros((180,180,3),np.float32);preset=dict(default_synth_preset(),width=180,height=180)
    p=params(turn_speed=0,tumble_speed=0,roll_speed=0)
    a=render_solid(arr,p,0,preset)
    assert np.array_equal(a,render_solid(arr,p,12,preset))
    for speed in ('turn_speed','tumble_speed','roll_speed'):
        assert not np.array_equal(a,render_solid(arr,dict(p,**{speed:30}),1,preset))
    moved=render_solid(arr,p,0,dict(preset,object_x=12))
    assert np.allclose(a[:,:-12],moved[:,12:],atol=1e-6)
    assert render_solid(arr,dict(p,model_data=''),0,preset) is arr
    assert render_solid(arr,dict(p,mix=0),0,preset) is arr
