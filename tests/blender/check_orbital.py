"""Blender integration check: --background --python this_file -- params.json."""
import sys,json,math
from pathlib import Path
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'assets/blender'))
import orbital_scene as scene
import bpy
params=json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text())
scene.build(params)
identity=dict(position=[0.,0.,0.],rotation=[0.,0.,0.],scale=[1.,1.,1.],visible=True,follow=True,material=None)

def snapshot():
    bpy.context.view_layer.update()
    return {key:bpy.data.objects[name].matrix_world.copy() for key,(name,_) in scene.PARTS.items()}

def same(a,b):return max(abs(a[i][j]-b[i][j]) for i in range(4) for j in range(4))<1e-5

for angle in (0.,.7,3.1,5.8):
    scene.pose(angle,params,{});before=snapshot()
    for key,(name,_) in scene.PARTS.items():
        scene.pose(angle,params,{key:dict(identity,position=[.2,.1,.3],rotation=[12.,23.,34.],scale=[1.2,.9,1.1])})
        changed=snapshot()
        assert all(same(before[k],changed[k]) == (k!=key) for k in before),(angle,key,'isolation')
        scene.pose(angle,params,{});assert all(same(v,snapshot()[k]) for k,v in before.items())
scene.pose(.8,params,{'ring2':dict(identity,follow=False,visible=False,material=dict(hue=.5,saturation=.9,metallic=.6,roughness=.2))})
obj=bpy.data.objects['Orbital ring 2'];custom=obj.data.materials[0];fixed=snapshot()['ring2']
assert obj.hide_render
scene.pose(1.8,params,{'ring2':dict(identity,follow=False,visible=False,material=dict(hue=.5,saturation=.9,metallic=.6,roughness=.2))})
assert same(snapshot()['ring2'],fixed)
scene.pose(1.8,params,{})
assert not obj.hide_render and obj.data.materials[0]!=custom
scene.pose(0.,params,{});before=snapshot();scene.pose(math.tau,params,{})
assert all(same(v,snapshot()[k]) for k,v in before.items()),'cycle seam'
print('ORBITAL_GEOMETRY_OK: eight isolated parts, restoration, material, visibility, frozen motion and loop seam')
