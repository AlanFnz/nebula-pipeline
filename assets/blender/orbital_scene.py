"""Painted nested rings, using the shared Blender worker, camera and part tools.

Only the procedural geometry and authored motion differ from Optical relic.
No reference pixels or pre-rendered video are used as source assets.
"""
import colorsys
import json
from pathlib import Path
from bisect import bisect_right
import math
import bpy
from mathutils import Vector, Matrix, Euler
import scene_worker as shared

PARTS = {'base': ('Orbital pedestal', (0,0,0)),
         **{'ring'+str(i): ('Orbital ring '+str(i), (0,0,0)) for i in range(1,6)},
         'core': ('Orbital core', (0,0,0)), 'finial': ('Orbital finial', (0,0,0))}
MOTION=json.loads(Path(__file__).with_name("orbital-motion-v1.json").read_text())
TRACKS=MOTION["tracks"]
frames = {}
bindings = {}


def empty(name, location=(0,0,0), parent=None):
    obj = bpy.data.objects.new(name,None); bpy.context.collection.objects.link(obj)
    obj.location = location; obj.parent = parent
    return obj


def painted(name, color, p):
    mat = shared.material(name, shared.linear(color), p['metallic'], p['roughness'])
    nodes=mat.node_tree.nodes; links=mat.node_tree.links
    shader=nodes.get('Principled BSDF')
    shader.inputs['Specular IOR Level'].default_value=.12
    coords=nodes.new('ShaderNodeTexCoord'); noise=nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value=105.; noise.inputs['Detail'].default_value=2.
    links.new(coords.outputs['Object'],noise.inputs['Vector'])
    bump=nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value=p['surface_grain']
    bump.inputs['Distance'].default_value=.013
    links.new(noise.outputs['Fac'],bump.inputs['Height']); links.new(bump.outputs['Normal'],shader.inputs['Normal'])
    mix=nodes.new('ShaderNodeMixRGB'); mix.blend_type='MULTIPLY'
    mix.inputs[0].default_value=p['surface_grain']*.55
    mix.inputs[1].default_value=(*shared.linear(color),1.)
    links.new(noise.outputs['Fac'],mix.inputs[2]); links.new(mix.outputs[0],shader.inputs['Base Color'])
    return mat


def annulus(name, radius, width, depth, bevel, mat, parent):
    n=192; verts=[]
    # Four concentric loops, all rings authored in their local XZ plane.
    for r,y in ((radius,-depth/2),(radius-width,-depth/2),(radius-width,depth/2),(radius,depth/2)):
        verts.extend((r*math.sin(j*math.tau/n),y,r*math.cos(j*math.tau/n)) for j in range(n))
    faces=[(k*n+j,k*n+(j+1)%n,((k+1)%4)*n+(j+1)%n,((k+1)%4)*n+j) for k in range(4) for j in range(n)]
    mesh=bpy.data.meshes.new(name); mesh.from_pydata(verts,[],faces); mesh.update()
    obj=bpy.data.objects.new(name,mesh); bpy.context.collection.objects.link(obj)
    shared.attach(obj,mat,parent)
    # Flat fronts retain a broad painted band; smooth cylindrical inside/outside.
    for i,face in enumerate(mesh.polygons): face.use_smooth = i//n in (1,3)
    mod=obj.modifiers.new('Soft painted edges','BEVEL'); mod.width=min(bevel,width*.45,depth*.45); mod.segments=4
    mod=obj.modifiers.new('Face normals','WEIGHTED_NORMAL'); mod.keep_sharp=True; mod.weight=50
    return obj


def cylinder(name,radius,depth,z,mat,bevel=.025):
    bpy.ops.mesh.primitive_cylinder_add(vertices=128,radius=radius,depth=depth,location=(0,0,z))
    obj=bpy.context.object;obj.name=name;shared.attach(obj,mat)
    for face in obj.data.polygons: face.use_smooth=len(face.vertices)==4
    mod=obj.modifiers.new('Turned edge','BEVEL'); mod.width=bevel;mod.segments=4
    obj.modifiers.new('Face normals','WEIGHTED_NORMAL')
    return obj


def join(objects,name,parent=None):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.select_set(True); bpy.context.view_layer.objects.active=obj
        for mod in list(obj.modifiers): bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.context.view_layer.objects.active=objects[0];bpy.ops.object.join()
    obj=objects[0];obj.name=name
    bpy.context.scene.cursor.location=(0,0,0);bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    obj.parent=parent
    return obj


def landscape_material(name,color,p,sky=False):
    mat=shared.material(name,shared.linear(color),rough=1.)
    nodes=mat.node_tree.nodes;links=mat.node_tree.links;shader=nodes.get('Principled BSDF')
    tex=nodes.new('ShaderNodeNewGeometry');mapping=nodes.new('ShaderNodeVectorMath');mapping.operation='MULTIPLY'
    mapping.inputs[1].default_value=(.25,1.,5.) if sky else (.25,5.,1.)
    offset=nodes.new('ShaderNodeVectorMath');offset.operation='ADD';offset.name='Landscape drift'
    links.new(tex.outputs['Position'],offset.inputs[0]);links.new(offset.outputs[0],mapping.inputs[0])
    noise=nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=.65;noise.inputs['Detail'].default_value=2.;noise.inputs['Roughness'].default_value=.6
    links.new(mapping.outputs[0],noise.inputs[0])
    wave=nodes.new('ShaderNodeTexWave');wave.bands_direction='Z' if sky else 'Y'
    wave.inputs['Scale'].default_value=.9 if sky else .45
    wave.inputs['Distortion'].default_value=1.5;wave.inputs['Detail Scale'].default_value=.35
    links.new(tex.outputs['Position'],wave.inputs['Vector'])
    phase=nodes.new('ShaderNodeMath');phase.operation='MULTIPLY';phase.inputs[1].default_value=8.
    links.new(noise.outputs['Fac'],phase.inputs[0]);links.new(phase.outputs[0],wave.inputs['Phase Offset'])
    stripe=nodes.new('ShaderNodeMath');stripe.operation='POWER';stripe.inputs[1].default_value=3.
    links.new(wave.outputs['Fac'],stripe.inputs[0])
    cloud=nodes.new('ShaderNodeValToRGB')
    cloud.color_ramp.elements[0].position=.34;cloud.color_ramp.elements[1].position=.68
    links.new(noise.outputs['Fac'],cloud.inputs[0])
    alpha=nodes.new('ShaderNodeMath');alpha.operation='MULTIPLY'
    links.new(stripe.outputs[0],alpha.inputs[0]);links.new(cloud.outputs[0],alpha.inputs[1])
    ramp=nodes.new('ShaderNodeMixRGB'); amount=p['stage_bands']
    ramp.inputs[1].default_value=(*shared.linear(color),1)
    ramp.inputs[2].default_value=(*shared.linear(tuple(min(1,v*(1+amount)) for v in color)),1)
    links.new(alpha.outputs[0],ramp.inputs[0]);links.new(ramp.outputs[0],shader.inputs['Base Color'])
    if sky:
        shader.inputs['Emission Strength'].default_value=1.
        links.new(ramp.outputs[0],shader.inputs['Emission Color'])
        shader.inputs['Base Color'].default_value=(0,0,0,1)
    else:
        shader.inputs['Emission Strength'].default_value=.25
        links.new(ramp.outputs[0],shader.inputs['Emission Color'])
    return mat


def build(p):
    global frames,bindings
    frames={};bindings={}
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    for collection in (bpy.data.meshes,bpy.data.curves,bpy.data.materials,bpy.data.cameras,bpy.data.lights):
        for data in list(collection):
            if data.users==0:collection.remove(data)
    scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=32;scene.cycles.use_denoising=True
    scene.cycles.seed=181126;scene.cycles.use_animated_seed=False;scene.cycles.max_bounces=6
    scene.render.threads_mode='FIXED';scene.render.threads=6
    scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGB';scene.render.image_settings.color_depth='8'
    scene.view_settings.view_transform='Standard';scene.view_settings.look='Medium High Contrast';scene.view_settings.exposure=p['exposure']
    scene.render.film_transparent=False;scene.world.use_nodes=True;scene.world.node_tree.nodes.clear()
    bg=scene.world.node_tree.nodes.new('ShaderNodeBackground');out=scene.world.node_tree.nodes.new('ShaderNodeOutputWorld')
    scene.world.node_tree.links.new(bg.outputs[0],out.inputs['Surface']);bg.inputs[0].default_value=(.76,.81,1,1);bg.inputs[1].default_value=p['environment']
    red=painted('Oxide red',colorsys.hsv_to_rgb(p['metal_hue'],p['metal_saturation'],p['paint_light']),p)
    cream=painted('Warm ivory',colorsys.hsv_to_rgb(p['accent_hue'],p['accent_saturation'],p['accent_light']),p)
    # Geometry scale is shared with Optical relic. Center remains above the base.
    shared.rotor=empty('Rotor',(0,0,.63+1.94*p['body_height']))
    shared.rotor.scale=(p['ring_width'],1,p['body_height'])
    width=p['band_width'];gap=p['ring_gap'];radius=1.94
    for i in range(1,6):
        key='ring'+str(i);f=empty('Motion / '+key,parent=shared.rotor);frames[key]=f
        annulus('Orbital ring '+str(i),radius-(i-1)*min(width+gap,.35),min(width,.28),p['band_depth'],p['edge_radius'],red if i%2 else cream,f)
    frames['core']=empty('Motion / core',parent=shared.rotor)
    shared.sphere('Orbital core',(0,0,0),p['core_size'],cream,frames['core'])
    foot=join([cylinder('Ivory foot',1.40,.18,.09,cream),cylinder('Red step',1.12,.18,.26,red),
               shared.lathe('Ivory cap',[(0,.32),(.80,.32),(.91,.37),(.87,.46),(.65,.55),(.2,.59),(0,.60)],cream)],'Orbital pedestal')
    foot.scale.x=foot.scale.y=p['base_width']
    top=.63+3.88*p['body_height']
    cap=join([cylinder('Collar',.30,.13,top+.08,cream,.06),shared.sphere('Red finial',(0,0,top+.25),.19,red)],'Orbital finial')
    # Finial scale is around its own local pivot.
    for v in cap.data.vertices:v.co.z-=top+.15
    cap.location.z=top+.15;cap.scale=(p['crown_size'],)*3
    # Floor ends at a physical backdrop; both keep contact shadows on the base.
    floor=landscape_material('Olive ground',colorsys.hsv_to_rgb(p['ground_hue'],p['ground_saturation'],p['ground_light']),p)
    sky=landscape_material('Painted blue sky',colorsys.hsv_to_rgb(p['background_hue'],p['background_saturation'],p['sky_light']),p,True)
    bpy.ops.mesh.primitive_plane_add(size=200);ground=bpy.context.object;ground.name='Ground';shared.attach(ground,floor)
    bpy.ops.mesh.primitive_plane_add(size=200,location=(0,p['horizon_depth'],100),rotation=(math.pi/2,0,0));wall=bpy.context.object;wall.name='Sky';shared.attach(wall,sky)
    wall.visible_shadow=False
    data=bpy.data.cameras.new('Camera');camera=bpy.data.objects.new('Camera',data);bpy.context.collection.objects.link(camera);scene.camera=camera
    target=Vector((0,0,2.39));az=math.radians(p['camera_yaw']);el=math.radians(p['camera_elevation'])
    camera.location=target+Vector((12*math.sin(az)*math.cos(el),-12*math.cos(az)*math.cos(el),12*math.sin(el)))
    shared.aim(camera,target);data.type='ORTHO'
    angle=math.radians(p['light_angle']);shared.area('Key', (5*math.sin(angle),-5*math.cos(angle),8),p['light_power'],p['light_size'],(1,.93,.78),(0,0,2.5))
    # Store authored parents so the same per-piece editor can add local offsets.
    for key,(name,pivot) in PARTS.items():
        obj=bpy.data.objects[name];bindings[key]=(obj.parent,obj.matrix_basis.copy(),tuple(obj.data.materials),{})


def measured_normal(key, phase):
    track=TRACKS[key]; phase%=1.
    index=max(0,bisect_right([row[0] for row in track],phase)-1)
    a=track[index]; b=track[index+1] if index+1<len(track) else [1.,*track[0][1:]]
    v0=Vector(a[1:]);v1=Vector(b[1:])
    if v0.dot(v1)<0: v1=-v1
    factor=(phase-a[0])/max(1e-8,b[0]-a[0])
    # Interpolate normals between authored poses for the continuous-motion option.
    return v0.lerp(v1,factor).normalized()


def pose(angle,p,overrides):
    for name in ('Olive ground','Painted blue sky'):
        node=bpy.data.materials[name].node_tree.nodes.get('Landscape drift')
        node.inputs[1].default_value=(math.sin(angle)*p.get('stage_motion',0.),0.,math.cos(angle)*p.get('stage_motion',0.))
    for i in range(1,6):
        key='ring'+str(i); f=frames[key]
        rate=p['orbit_turns_'+str(i)]; phase=p['orbit_phase_'+str(i)]/360.
        if i==1:
            # The authored exposures have slightly uneven frame holds. Advance
            # the outer axle by an equal angle per pose, as in the reference.
            steps=MOTION['steps']; a=(angle/math.tau)%1.
            j=max(0,bisect_right(steps,a+1e-8)-1)
            end=steps[j+1] if j+1<len(steps) else 1.
            angle_outer=math.tau*(j+(a-steps[j])/max(1e-8,end-steps[j]))/len(steps)
        else: angle_outer=angle
        tilt=math.radians(p['orbit_tilt_'+str(i)])
        if i>1 and p.get('orbit_tumble',1.):
            n=measured_normal(key,angle/math.tau*rate+phase)
            measured=Vector((0,-1,0)).rotation_difference(n)
            axial=Euler((0.,0.,angle*rate+phase*math.tau),'XYZ').to_quaternion()
            rotation=axial.slerp(measured,p['orbit_tumble']).to_matrix().to_4x4()
        else: rotation=Matrix.Rotation(angle_outer*rate+phase*math.tau,4,'Z')
        f.rotation_euler=(Matrix.Rotation(tilt,4,'Y') @ rotation).to_euler()
    for key,(name,_) in PARTS.items():
        obj=bpy.data.objects[name];parent,matrix,materials,copies=bindings[key];edit=overrides.get(key)
        obj.parent=parent;obj.matrix_basis=matrix
        if edit:
            if not edit['follow'] and parent:
                obj.parent=None;obj.matrix_basis=shared.rotor.matrix_basis @ matrix
            delta=(Matrix.Translation(Vector(edit['position'])) @ Euler(tuple(math.radians(v) for v in edit['rotation']),'XYZ').to_matrix().to_4x4() @ Matrix.Diagonal((*edit['scale'],1.)))
            obj.matrix_basis=obj.matrix_basis @ delta
        obj.hide_render=bool(edit and not edit['visible'])
        settings=edit.get('material') if edit else None
        for index,original in enumerate(materials):
            if settings is None:obj.data.materials[index]=original;continue
            if index not in copies:copies[index]=original.copy()
            mat=copies[index];obj.data.materials[index]=mat
            nodes=mat.node_tree.nodes;links=mat.node_tree.links
            shader=nodes.get('Principled BSDF')
            # Own color replaces the painted base while retaining its surface bump.
            for link in list(shader.inputs['Base Color'].links):links.remove(link)
            shader.inputs['Base Color'].default_value=(*shared.linear(colorsys.hsv_to_rgb(settings['hue'],settings['saturation'],.82)),1.)
            shader.inputs['Metallic'].default_value=settings['metallic'];shader.inputs['Roughness'].default_value=settings['roughness']
