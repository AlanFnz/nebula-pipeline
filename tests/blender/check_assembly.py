"""Run with Blender --background --factory-startup --python this_file -- params.json."""
import json
from pathlib import Path
import sys
import math

sys.dont_write_bytecode = True
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'assets/blender'))
import assembly_worker as worker
from mathutils import Matrix, Euler

params=json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text())
worker.base.build(params); worker.remember()
bpy=worker.base.bpy
bpy.context.view_layer.update()
original={key: saved['obj'].matrix_world.copy() for key,saved in worker.pieces.items()}
original_material={key: saved['obj'].data.materials[0] for key,saved in worker.pieces.items()}
identity=dict(position=[0.,0.,0.],rotation=[0.,0.,0.],scale=[1.,1.,1.],visible=True,material=None)

def close(a,b):
    return all(abs(a[i][j]-b[i][j])<2e-6 for i in range(4) for j in range(4))

for key,saved in worker.pieces.items():
    follow=saved['parent'] is not None
    worker.apply_parts({key:dict(identity,follow=follow,position=[.25,-.1,.3],rotation=[15.,30.,45.],scale=[1.2,.8,1.1])})
    bpy.context.view_layer.update()
    for other,piece in worker.pieces.items():
        assert close(piece['obj'].matrix_world,original[other]) == (key!=other),(key,other)
    worker.apply_parts({}); bpy.context.view_layer.update()
    assert all(close(piece['obj'].matrix_world,original[name]) for name,piece in worker.pieces.items())

key='upper'; saved=worker.pieces[key]
before=original[key] @ saved['matrix'].inverted() @ saved['pivot']
worker.apply_parts({key:dict(identity,follow=True,rotation=[50.,10.,20.],scale=[1.4,.7,1.2])})
bpy.context.view_layer.update()
after=saved['obj'].matrix_world @ saved['matrix'].inverted() @ saved['pivot']
assert (before-after).length<2e-6,'Rotation/scale moved the part pivot'

worker.apply_parts({'crown':dict(identity,follow=False,material=dict(hue=.9,saturation=.8,metallic=.2,roughness=.6))})
bpy.context.view_layer.update(); fixed=worker.pieces['crown']['obj'].matrix_world.copy()
worker.base.rotor.rotation_euler.z=1.2; bpy.context.view_layer.update()
assert close(fixed,worker.pieces['crown']['obj'].matrix_world),'Detached part followed assembly rotation'
assert not close(original['upper'],worker.pieces['upper']['obj'].matrix_world)
assert worker.pieces['crown']['obj'].data.materials[0] != original_material['crown']
assert all(p['obj'].data.materials[0] == original_material[k] for k,p in worker.pieces.items() if k!='crown')
worker.apply_parts({}); worker.base.rotor.rotation_euler.z=0.; bpy.context.view_layer.update()
assert all(close(p['obj'].matrix_world,original[k]) for k,p in worker.pieces.items())
assert all(p['obj'].data.materials[0] == original_material[k] for k,p in worker.pieces.items())
worker.apply_parts({'left':dict(identity,follow=True,visible=False)})
assert worker.pieces['left']['obj'].hide_render
assert all(not p['obj'].hide_render for k,p in worker.pieces.items() if k!='left')
worker.apply_parts({}); assert not worker.pieces['left']['obj'].hide_render

# Width/height changes must not distort an independent part's rotation when
# Follow assembly changes. Compare the complete transform, not just its center.
worker.base.build(dict(params,ring_width=1.3,body_height=.7)); worker.remember()
for key,saved in worker.pieces.items():
    for follow in (False,True):
        pose=dict(identity,follow=follow,position=[.2,.3,-.1],rotation=[27.,41.,12.],scale=[1.3,.7,1.1])
        delta=(Matrix.Translation(saved['pivot']+worker.Vector(pose['position'])) @
               Euler(tuple(math.radians(v) for v in pose['rotation']),'XYZ').to_matrix().to_4x4() @
               Matrix.Diagonal((*pose['scale'],1.)) @ Matrix.Translation(-saved['pivot']))
        source=worker.rotor_bind if saved['parent'] else Matrix.Identity(4)
        worker.base.rotor.rotation_euler.z=.8
        worker.apply_parts({key:pose}); bpy.context.view_layer.update()
        expected=source @ delta @ saved['matrix']
        if follow: expected=worker.base.rotor.matrix_world @ worker.rotor_bind.inverted() @ expected
        assert close(saved['obj'].matrix_world,expected),(key,follow,'nonuniform assembly scale')
worker.apply_parts({})
print('ASSEMBLY_GEOMETRY_OK: 7 isolated transforms, own pivot, independent rotation, nonuniform scale, material, visibility and reset')
