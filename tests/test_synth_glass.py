import copy
import numpy as np
from synth_solids import render_solid,hidden_controls
from synth_mesh import decode_mesh
from test_synth_mesh import params
from synth import default_synth_preset
from synth_starters import starter_composition
from synth_composition import compile_composition
from synth_sequence import render_sequence_frame


def test_height_keeps_width_and_depth_and_does_not_modify_asset():
    p=params(yaw=0,pitch=0,roll=0,turn_speed=0,tumble_speed=0,roll_speed=0,perspective=0,scale=.4)
    arr=np.zeros((256,256,3),np.float32);preset=dict(default_synth_preset(),width=256,height=256)
    original=decode_mesh(p['model_data'])[0].copy()
    a,b=[render_solid(arr,dict(p,height_stretch=height),0,preset).max(2)>0 for height in (1,2)]
    assert np.flatnonzero(a.any(0)).tolist()==np.flatnonzero(b.any(0)).tolist()
    assert abs(b.any(1).sum()-2*a.any(1).sum())<=2
    assert np.array_equal(original,decode_mesh(p['model_data'])[0])


def test_glass_changes_with_rotation_and_transmission_but_preserves_background():
    arr=np.empty((128,128,3),np.float32)
    yy,xx=np.mgrid[:128,:128];arr[:]=np.stack((xx/128,yy/128,np.full_like(xx,.3,dtype=float)),axis=-1)
    preset=dict(default_synth_preset(),width=128,height=128)
    p=params(material=2,scale=.45,height_stretch=1.4,turn_speed=24,specular=.9)
    before=arr.copy()
    a=render_solid(arr,p,0,preset)
    assert np.isfinite(a).all()
    assert np.array_equal(arr,before)
    assert np.allclose(a[:8],arr[:8],atol=1e-7) and np.allclose(a[-8:],arr[-8:],atol=1e-7)
    assert np.array_equal(a,render_solid(arr,p,0,preset))
    for change in ({'glass_transmission':.5},{'glass_refraction':.6},{'roughness':.9},{'specular':0}):
        assert not np.array_equal(a,render_solid(arr,dict(p,**change),0,preset))
    assert not np.array_equal(a,render_solid(arr,p,1,preset))
    opaque=dict(p,glass_transmission=0)
    assert np.array_equal(render_solid(arr,opaque,0,preset),render_solid(arr,dict(opaque,glass_refraction=.6),0,preset))
    for shape in (0,1):
        output=render_solid(arr,dict(p,shape=shape,corner_radius=.1),0,preset)
        assert np.isfinite(output).all() and not np.array_equal(output,arr)


def test_glass_controls_follow_material_and_shape():
    ranges={'solid.shape':(2,2),'solid.material':(2,2)}
    assert 'solid.glass_transmission' not in hidden_controls(ranges)
    assert 'solid.height_stretch' not in hidden_controls(ranges)
    assert 'solid.shading' in hidden_controls(ranges)
    assert 'solid.height_stretch' in hidden_controls(dict(ranges,**{'solid.shape':(0,0)}))
    assert 'solid.glass_transmission' in hidden_controls(dict(ranges,**{'solid.material':(1,1)}))


def test_saved_crystal_preserves_background_and_rotation(tmp_path):
    from synth_composition import save_composition,load_composition
    project=starter_composition('color-film-die');before=copy.deepcopy(project)
    project['effects']['solid']={'mode':'on','params':{'solid.shape':2,'solid.model_data':params()['model_data'],
        'solid.material':2,'solid.height_stretch':1.75,'solid.glass_transmission':.08,'solid.glass_refraction':.24}}
    path=tmp_path/'crystal.json';save_composition(path,project)
    loaded=load_composition(path)
    assert loaded['source']==before['source']
    seq=compile_composition(loaded)
    a=render_sequence_frame(seq,1.,(120,180)).tobytes()
    assert a==render_sequence_frame(compile_composition(project),1.,(120,180)).tobytes()
