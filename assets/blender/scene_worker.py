"""Nebula's bundled scene builder. Executed ONLY by Blender, never imported by Qt.

The stdin/stdout protocol accepts numeric scene settings, not Python or blend
files. A persistent process keeps Blender and its render device warm.
"""
import colorsys
import json
import math
import os
import sys
import traceback

import bpy
from mathutils import Vector

PROTOCOL = 'NEBULA_FRAME '
scene_key = None
rotor = None


def linear(color):
    return tuple(v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in color)


def material(name, color, metal=0., rough=.5):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (*color, 1.)
    bsdf.inputs['Metallic'].default_value = metal
    bsdf.inputs['Roughness'].default_value = rough
    return mat


def attach(obj, mat, parent=None):
    obj.data.materials.append(mat)
    if parent: obj.parent = parent
    if obj.type == 'MESH':
        for face in obj.data.polygons: face.use_smooth = True
    return obj


def lathe(name, profile, mat, parent=None, axis='Z', location=(0, 0, 0)):
    # Catmull-Rom interpolation preserves the authored turned profile.
    samples = []
    padded = [profile[0], *profile, profile[-1]]
    for i in range(1, len(padded)-2):
        a, b, c, d = (Vector(p) for p in padded[i-1:i+3])
        for j in range(6):
            t = j / 6
            p = .5*((2*b)+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t*t*t)
            samples.append((max(.0001, p.x), p.y))
    samples.append(profile[-1])
    n = 96
    vertices = [(r*math.cos(j*math.tau/n), r*math.sin(j*math.tau/n), z)
                for r,z in samples for j in range(n)]
    faces = [(i*n+j, i*n+(j+1)%n, (i+1)*n+(j+1)%n, (i+1)*n+j)
             for i in range(len(samples)-1) for j in range(n)]
    faces.extend([tuple(reversed(range(n))), tuple((len(samples)-1)*n+j for j in range(n))])
    mesh = bpy.data.meshes.new(name); mesh.from_pydata(vertices, [], faces); mesh.update()
    obj = bpy.data.objects.new(name, mesh); bpy.context.collection.objects.link(obj)
    obj.location = location
    if axis == 'X': obj.rotation_euler[1] = math.pi/2
    return attach(obj, mat, parent)


def sphere(name, position, radius, mat, parent=None):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=radius, location=position)
    obj = bpy.context.object; obj.name = name
    return attach(obj, mat, parent)


def oval(name, center, width, height, thickness, bow_depth, twist, mat, parent):
    curve = bpy.data.curves.new(name, 'CURVE'); curve.dimensions = '3D'
    curve.bevel_depth = thickness; curve.bevel_resolution = 5
    spline = curve.splines.new('POLY'); spline.points.add(127)
    for i, point in enumerate(spline.points):
        t = math.tau*i/128
        bow = bow_depth*math.sin(2*t) + (twist if center>3 else -twist)*math.sin(t)
        point.co = (width*math.sin(t), bow, center+height*math.cos(t), 1)
    spline.use_cyclic_u = True
    obj = bpy.data.objects.new(name, curve); bpy.context.collection.objects.link(obj)
    return attach(obj, mat, parent)


def aim(obj, point):
    obj.rotation_euler = (Vector(point)-obj.location).to_track_quat('-Z', 'Y').to_euler()


def area(name, position, power, size, color, target):
    data = bpy.data.lights.new(name, 'AREA'); data.energy = power; data.shape = 'DISK'; data.size = size; data.color = color
    obj = bpy.data.objects.new(name, data); bpy.context.collection.objects.link(obj)
    obj.location = position; aim(obj, target)


def build(p):
    global rotor
    if p['scene_version'] != 1: raise ValueError('Unsupported Blender scene version')
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
    for collection in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for data in list(collection):
            if data.users == 0: collection.remove(data)
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 32
    scene.cycles.use_denoising = True
    scene.cycles.seed = 161126
    scene.cycles.use_animated_seed = False
    scene.cycles.max_bounces = 6
    scene.render.threads_mode = 'FIXED'; scene.render.threads = 6
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.color_depth = '8'
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Medium High Contrast'
    scene.view_settings.exposure = p['exposure']
    scene.render.film_transparent = False
    import studio_stage
    metal = studio_stage.environment(p)
    # The foot is stationary; the assembly above it turns on its vertical axis.
    base = lathe('Turned foot', [(0.,.025),(.65,.025),(.94,.06),(1.,.11),(.93,.17),
        (.78,.25),(.64,.59),(.46,.74),(.26,.81),(.19,.88),(.20,.93),(.30,.97),
        (.30,1.01),(.19,1.06),(.14,1.14),(.12,1.24),(.17,1.33),(0.,1.37)], metal)
    base.scale.x = base.scale.y = p['base_width']*1.1
    base.scale.z = 1.18
    rotor = bpy.data.objects.new('Rotor', None); bpy.context.collection.objects.link(rotor)
    rotor.scale = (p['ring_width'], 1., p['body_height'])
    rotor.location.z = .10+1.3*(1-p['body_height'])
    # Elliptical hoops meet at the equatorial hub, as in the reference.
    oval('Upper hoop', 3.86, .76, .78, p['tube_radius'], p['hoop_bow'], p['hoop_twist'], metal, rotor)
    oval('Lower hoop', 2.29, .76, .78, p['tube_radius'], p['hoop_bow'], p['hoop_twist'], metal, rotor)
    lathe('Central spindle', [(0.,1.25),(.14,1.30),(.13,1.48),(.08,1.62),
        (.08,1.78),(.20,1.91),(.20,2.01),(.12,2.05),(.10,2.19),(.26,2.26),
        (.27,2.34),(.16,2.41),(.14,2.54),(.36,2.64),(.54,2.84),(.59,3.10),
        (.53,3.36),(.34,3.55),(.14,3.65),(.14,3.68),(.24,3.73),(.25,3.80),
        (.15,3.84),(.16,4.06),(.23,4.15),(.23,4.27),(.13,4.37),(.16,4.48),
        (.22,4.52),(.22,4.58),(.12,4.63),(0.,4.66)], metal, rotor)
    sphere('Crown', (0,0,4.96), .38*p['crown_size'], metal, rotor)
    for sign in (-1, 1):
        # Each short cross-axis pin has a collar and a rounded terminal.
        pin = lathe('Axle '+str(sign),[(0.,0.),(.13,.03),(.14,.58),(.22,.65),
            (.22,.72),(.12,.78),(.12,.86),(.22,.90),(.24,1.01),(.17,1.10),(0.,1.13)],
            metal, rotor, axis='X', location=(0,0,3.09))
        pin.rotation_euler[1] = sign*math.pi/2
        pin.scale.z = p['axle_length']
    camera_data = bpy.data.cameras.new('Camera'); camera = bpy.data.objects.new('Camera',camera_data)
    bpy.context.collection.objects.link(camera); scene.camera = camera
    target = Vector((0, 0, 2.64))
    az, el = math.radians(p['camera_yaw']), math.radians(p['camera_elevation'])
    camera.location = target+Vector((12*math.sin(az)*math.cos(el),-12*math.cos(az)*math.cos(el),12*math.sin(el)))
    aim(camera, target)
    camera_data.type = 'ORTHO'; camera_data.ortho_scale = 5.8/p['size']
    studio_stage.lights(p)


def configure_device():
    try:
        preferences = bpy.context.preferences.addons['cycles'].preferences
        preferences.compute_device_type = 'METAL'
        preferences.get_devices()
        gpu = False
        for device in preferences.devices:
            device.use = device.type == 'METAL'
            gpu |= device.use
        bpy.context.scene.cycles.device = 'GPU' if gpu else 'CPU'
    except Exception:
        bpy.context.scene.cycles.device = 'CPU'


def frame_camera(scene, p, size):
    w,h = size
    scene.render.resolution_x = w; scene.render.resolution_y = h
    scene.render.resolution_percentage = 100
    # Blender's ortho scale is the width for landscape, height for portrait.
    scene.camera.data.ortho_scale = 5.8/p['size'] * max(1., w/h) * p.get('framing_height',1.)
    scene.camera.data.shift_x = -p.get('offset_x',0.)*w/max(w,h)
    scene.camera.data.shift_y = p.get('offset_y',0.)*h/max(w,h)
    import studio_stage
    studio_stage.fit_to_camera(scene)


def render(request):
    global scene_key
    p = request['params']
    key = json.dumps(p, sort_keys=True)
    if key != scene_key:
        build(p); configure_device(); scene_key = key
    rotor.rotation_euler.z = request['angle']
    scene = bpy.context.scene
    frame_camera(scene,p,request['size'])
    scene.render.filepath = request['output']
    if request.get('blend_output'):
        bpy.ops.wm.save_as_mainfile(filepath=request['blend_output'])
    bpy.ops.render.render(write_still=True)
    return {'ok': True, 'output': request['output'], 'device': scene.cycles.device}


def main():
    print(PROTOCOL+json.dumps({'ready':True, 'version':bpy.app.version_string}), flush=True)
    for line in sys.stdin:
        try:
            request = json.loads(line)
            if request.get('quit'): break
            result = render(request)
        except Exception as exc:
            traceback.print_exc()
            result = {'ok':False,'error':str(exc)}
        print(PROTOCOL+json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
