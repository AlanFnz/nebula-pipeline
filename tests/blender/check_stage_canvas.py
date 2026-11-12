"""Run with Blender --background --python this_file -- request_directory."""
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'assets/blender'))
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
import scene_worker as shared
import studio_stage
import orbital_scene
import orbital_variants

folder = Path(sys.argv[sys.argv.index('--')+1])
formats = [(720,900,1.), (1080,1350,1.5), (1920,1080,1.2),
           (1080,1920,1920/900), (4096,64,64/900),
           (64,4096,4096/900), (4096,4096,4096/900)]
checked = 0
for name in ('relic','painted','yin'):
    params = json.loads((folder/(name+'-request.json')).read_text())['params']
    for elevation,yaw in ((10.,0.), (0.,0.), (1.,-60.), (45.,60.)):
        p = dict(params,camera_elevation=elevation,camera_yaw=yaw)
        if p.get('scene',0):
            orbital_scene.build(p)
            if p.get('orbital_finish',0): orbital_variants.apply(p)
        else:
            shared.build(p)
        scene = bpy.context.scene
        camera = scene.camera
        bpy.context.view_layer.update()
        original_camera = camera.location.copy()
        stages = [bpy.data.objects[n] for n in ('Seamless floor','Ground','Sky') if n in bpy.data.objects]
        original_meshes = {obj.name:[v.co.copy() for v in obj.data.vertices] for obj in stages}
        for w,h,framing in formats:
            for dx,dy in ((0.,0.),(.35,-.25)):
                shared.frame_camera(scene,dict(p,framing_height=framing,offset_x=dx,offset_y=dy),(w,h))
                bpy.context.view_layer.update()
                deps = bpy.context.evaluated_depsgraph_get()
                corners = camera.data.view_frame(scene=scene)
                left,right = min(v.x for v in corners),max(v.x for v in corners)
                bottom,top = min(v.y for v in corners),max(v.y for v in corners)
                direction = camera.rotation_euler.to_quaternion() @ Vector((0,0,-1))
                for x in range(13):
                    for y in range(17):
                        local = Vector((left+(right-left)*(x+.01)/12.02,
                                        bottom+(top-bottom)*(y+.01)/16.02,0))
                        origin = camera.matrix_world @ local
                        hit = scene.ray_cast(deps,origin+direction*camera.data.clip_start,direction,
                                             distance=camera.data.clip_end)
                        assert hit[0] and not hit[4].hide_render, (name,elevation,yaw,w,h,dx,dy,x,y)
                        checked += 1
                # Axial retreat cannot move or scale any point in the image.
                points = [Vector((0,0,z)) for z in (0.,2.,5.)]
                fitted = [world_to_camera_view(scene,camera,v) for v in points]
                camera.location = original_camera
                bpy.context.view_layer.update()
                authored = [world_to_camera_view(scene,camera,v) for v in points]
                assert all((a.xy-b.xy).length<1e-4 for a,b in zip(fitted,authored))
        # Restore a compact viewport after widening/offsetting the same scene.
        shared.frame_camera(scene,dict(p,framing_height=1.,offset_x=0.,offset_y=0.),(720,900))
        if elevation==10. and yaw==0.:
            assert camera.location==original_camera
            assert all([v.co for v in obj.data.vertices]==original_meshes[obj.name] for obj in stages)
print(f'STAGE_CANVAS_OK: {checked} rays covered, unchanged projection, authored stage restored')
