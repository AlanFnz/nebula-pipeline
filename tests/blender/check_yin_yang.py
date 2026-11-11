"""Run in Blender: --background --python this_file -- params.json."""
import sys, json, math
from pathlib import Path
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'assets/blender'))
import bpy
import orbital_scene as scene
import orbital_variants as variants
from mathutils import Matrix

# Smoothing is opt-in and periodic, including its velocity at the loop seam.
for key,track in scene.TRACKS.items():
    for sample in track:
        phase=sample[0]
        assert scene.orbit_normal(key,phase,0.)==scene.measured_normal(key,phase)
        fitted=scene.orbit_normal(key,phase,1.)
        assert abs(fitted.length-1.)<1e-5
        assert (fitted-scene.orbit_normal(key,phase+1.,1.)).length<1e-5
    h=.00001
    left=(scene.orbit_normal(key,0.,1.)-scene.orbit_normal(key,-h,1.))/h
    right=(scene.orbit_normal(key,h,1.)-scene.orbit_normal(key,0.,1.))/h
    assert (left-right).length<.2
# The tracked path recoils briefly before continuing around the 7–8 s region.
assert scene.measured_normal('ring2',.133).x>scene.measured_normal('ring2',.120).x
assert scene.orbit_normal('ring2',.133,1.).x<scene.orbit_normal('ring2',.120,1.).x
x=[scene.orbit_normal('ring2',.08+i*.0002,1.).x for i in range(601)]
directions=[b>a for a,b in zip(x,x[1:])]
assert sum(a!=b for a,b in zip(directions,directions[1:]))==1

p=json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text())
scene.build(p);variants.apply(p)
identity=dict(position=[0.,0.,0.],rotation=[0.,0.,0.],scale=[1.,1.,1.],visible=True,follow=True,material=None)
hidden={k:dict(identity,visible=False) for k in ('ring3','ring4','ring5','core')}
scene.pose(0.,p,hidden)
assert {key for key,(name,_) in scene.PARTS.items() if not bpy.data.objects[name].hide_render}=={'base','ring1','ring2','finial'}
assert bpy.context.scene.view_settings.view_transform=='AgX'
assert all(bpy.data.objects.get(name) for name in ('Seamless floor','Key softbox','Green fill','Top reflection'))
assert all(not bpy.data.objects.get(name) for name in ('Ground','Sky','Key'))
disc=bpy.data.objects['Orbital ring 2']
assert len([f for f in disc.data.polygons if len(f.vertices)>4])==2  # both faces capped
assert max(v.co.y for v in disc.data.vertices)-min(v.co.y for v in disc.data.vertices)>.25
mat=disc.data.materials[0]
assert mat.node_tree.nodes.get('Yin colors')
original=disc.matrix_basis.copy()
scene.pose(.7,p,dict(hidden,ring2=dict(identity,rotation=[25,10,0],material=dict(hue=.6,saturation=.8,metallic=.7,roughness=.3))))
assert disc.matrix_basis!=original
custom=disc.data.materials[0]
assert custom!=mat and custom.node_tree.nodes['Principled BSDF'].inputs['Base Color'].is_linked
assert custom.node_tree.nodes['Yin colors'].inputs[1].default_value!=mat.node_tree.nodes['Yin colors'].inputs[1].default_value
scene.pose(.7,p,hidden)
assert disc.data.materials[0]==mat and disc.matrix_basis==original
scene.pose(0.,p,hidden);bpy.context.view_layer.update();start=disc.matrix_world.copy()
scene.pose(math.tau,p,hidden);bpy.context.view_layer.update()
assert max(abs(start[i][j]-disc.matrix_world[i][j]) for i in range(4) for j in range(4))<1e-5
# A printed symbol makes the legacy shortest-arc roll singularity visible.
# The symbol follows the selected normals without an abrupt 50° flip.
previous=None
for frame in range(226):
    scene.pose(math.tau*frame/226,p,hidden)
    current=scene.frames['ring2'].rotation_euler.to_quaternion()
    if previous is not None:
        angle=math.degrees(previous.rotation_difference(current).angle)%360
        assert min(angle,360-angle)<15
    previous=current
# Build the legacy scene after a custom studio: no leaked geometry, light or material.
scene.build(dict(p,orbital_finish=0,orbit_shape_2=0));scene.pose(0.,p,{})
assert bpy.data.objects.get('Ground') and bpy.data.objects.get('Sky')
assert not bpy.data.objects.get('Seamless floor')
assert all(not bpy.data.objects[name].hide_render for name,_ in scene.PARTS.values())
assert not bpy.data.objects['Orbital ring 2'].data.materials[0].node_tree.nodes.get('Yin colors')
print('YIN_YANG_OK: capped disc, shared studio, isolated edits, symbol-preserving material, loop and legacy restoration')
