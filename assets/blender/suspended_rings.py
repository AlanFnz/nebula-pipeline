"""An alternative arrangement of the orbital assembly in a reflected light tent."""
import colorsys
import json
import math
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy
from mathutils import Euler, Matrix, Vector

import orbital_scene as orbital
import reflection_stage
import scene_worker as shared


pieces = {}
output = shared.render
ortho_camera = shared.frame_camera


def round_band(name, outer, width, p, material, parent):
    """Sections of one gently convex lens. Both faces carry the same curvature."""
    inner = outer - width
    edge = min(max(.0001, p['edge_radius']), width*.47)
    profile = []
    def point(radius, side):
        half_depth = p['band_depth']*.5 + .28*p['face_camber']*(1 - (radius/1.94)**2)
        profile.append((radius, side*half_depth))
    for j in range(25):
        t = -math.pi/2 + math.pi*j/24
        point(outer-edge + edge*math.cos(t), math.sin(t))
    for j in range(1,8):
        point(outer-edge - (width-2*edge)*j/8, 1.)
    for j in range(25):
        t = math.pi/2 + math.pi*j/24
        point(inner+edge + edge*math.cos(t), math.sin(t))
    for j in range(1,8):
        point(inner+edge + (width-2*edge)*j/8, -1.)
    # Revolve the cross section around the same local Y axis as the other orbital parts.
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([(0., y, r) for r, y in profile],
                     [(i, (i+1) % len(profile)) for i in range(len(profile))], [])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    shared.attach(obj, material, parent)
    lathe = obj.modifiers.new('Polished band', 'SCREW')
    lathe.axis = 'Y'
    lathe.steps = lathe.render_steps = 192
    lathe.use_smooth_shade = True
    lathe.use_merge_vertices = True
    return obj


def frame_camera(scene, p, size):
    width, height = size
    squeeze = p['lens_squeeze']
    scene.render.pixel_aspect_x = max(1., 1/squeeze)
    scene.render.pixel_aspect_y = max(1., squeeze)
    ortho_camera(scene, p, size)
    aspect = width/(height*squeeze)
    camera = scene.camera
    field_height = 5.8 / p['size'] * p.get('framing_height', 1.)
    if p['perspective'] > 0:
        distance = 1.94 / p['perspective']
        camera.location = camera.rotation_euler.to_matrix() @ Vector((0, 0, distance))
        camera.data.type = 'PERSP'
        camera.data.sensor_fit = 'VERTICAL'
        camera.data.lens = distance * camera.data.sensor_height / field_height
        camera.data.clip_end = max(100., distance + 20.)
        divisor = 1.
    else:
        divisor = max(1., aspect)
        camera.data.ortho_scale = field_height * divisor
    camera.data.shift_x = -p.get('offset_x', 0.) * aspect / divisor
    camera.data.shift_y = p.get('offset_y', 0.) / divisor


def build(p):
    pieces.clear()
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for collection in (bpy.data.meshes, bpy.data.cameras, bpy.data.materials, bpy.data.images):
        for item in list(collection):
            if not item.users:
                collection.remove(item)
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 8
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 6
    scene.cycles.seed = 1
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = 6
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.color_depth = '8'
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.view_settings.exposure = p['exposure']
    scene.world.color = (.02,.02,.02)
    data = bpy.data.cameras.new('Camera')
    camera = bpy.data.objects.new('Camera', data)
    bpy.context.collection.objects.link(camera)
    az, el = (math.radians(p[key]) for key in ('camera_yaw', 'camera_elevation'))
    camera.location = (12*math.sin(az)*math.cos(el), -12*math.cos(az)*math.cos(el), 12*math.sin(el))
    shared.aim(camera, (0,0,0))
    data.type = 'ORTHO'
    scene.camera = camera
    reflection_stage.build(p)
    metal = shared.material('Polished alloy', shared.linear(reflection_stage.color(p, 'metal')),
                            p['metallic'], p['roughness'])
    bsdf = metal.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Transmission Weight'].default_value = p['transmission']
    bsdf.inputs['IOR'].default_value = p['ior']
    bsdf.inputs['Coat Weight'].default_value = p['angle_tint']*.44
    bsdf.inputs['Coat Roughness'].default_value = p['roughness']*.65
    reflection_stage.coat_material(metal, p['angle_tint'])
    reflection_stage.tint(metal, reflection_stage.color(p, 'metal'))
    reflection_stage.surface_texture(metal, p['surface_grain'])
    shared.rotor = orbital.empty('Ring assembly')
    shared.rotor.scale = (p['ring_width'], 1., p['body_height'])
    count = p['ring_count']
    core = p['core_size']
    outer = 1.94
    # The bands taper towards the hub. Spacing, fill and hub size are independent.
    weights = [1+.065*(count-1-i) for i in range(count)]
    span = (outer-core)/sum(weights)
    for i, weight in enumerate(weights, 1):
        key = 'ring'+str(i)
        frame = orbital.empty('Axis / '+key, parent=shared.rotor)
        step = weight*span
        gap = min(p['ring_gap'], step*.80)
        width = (step-gap)*p['band_width']/.40
        # The rim rounds into the side wall along the full depth. A narrow
        # frontal highlight can thus turn into a broad highlight at grazing angles.
        obj = round_band('Band '+str(i), outer, width, p, metal, frame)
        pieces[key] = (obj, frame)
        outer -= step
    frame = orbital.empty('Hub axis', parent=shared.rotor)
    hub = orbital.cylinder('Center disc', core, p['band_depth'], 0., metal, min(p['edge_radius'],core*.4))
    hub.data.transform(Matrix.Rotation(math.pi/2, 4, 'X'))
    hub.parent = frame
    pieces['core'] = (hub, frame)


def pose(angle, p, edits):
    for key, (obj, frame) in pieces.items():
        edit = edits.get(key, {})
        obj.hide_render = not edit.get('visible', True)
        axis = Matrix.Identity(4)
        if edit.get('follow', True):
            if key == 'core':
                axis = Matrix.Rotation(angle, 4, 'Z')
            else:
                n = key[4:]
                rate = p['orbit_turns_'+n]
                offset = math.radians(p['orbit_phase_'+n])
                tilt = Matrix.Rotation(math.radians(p['orbit_tilt_'+n]), 4, 'Y')
                pace, drift = p.get('orbit_pace_'+n, 0.), p.get('orbit_drift_'+n, 0.)
                # Each half turn closes into a single face. A varied ring can
                # arrive late at the crossing and still meet its neighbors.
                separation = math.sin(angle)**2
                t = angle - .72*pace*separation
                axis = tilt @ Matrix.Rotation(t*rate+offset, 4, 'Z') @ tilt.transposed()
                if drift:
                    phases = orbital.motion_phases(int(n), p.get('orbit_pattern', 0))
                    axis = orbital.axis_drift(angle/math.tau, drift*separation, phases) @ axis
        frame.matrix_basis = axis
        obj.location = edit.get('position', (0,0,0))
        obj.rotation_euler = Euler(tuple(math.radians(v) for v in edit.get('rotation', (0,0,0))))
        obj.scale = edit.get('scale', (1,1,1))
        own = edit.get('material')
        if own:
            mat = bpy.data.materials.get('Alloy / '+key) or bpy.data.materials['Polished alloy'].copy()
            mat.name = 'Alloy / '+key
            shader = mat.node_tree.nodes['Principled BSDF']
            color = colorsys.hsv_to_rgb(own['hue'], own['saturation'], own.get('light', .82))
            reflection_stage.tint(mat, color)
            shader.inputs['Metallic'].default_value = own['metallic']
            shader.inputs['Roughness'].default_value = own['roughness']
        else:
            mat = bpy.data.materials['Polished alloy']
        obj.data.materials[0] = mat


def render(request):
    p = request['params']
    key = json.dumps(p, sort_keys=True)
    if key != shared.scene_key:
        build(p)
        shared.configure_device()
        shared.scene_key = key
    pose(request['angle'], p, request.get('parts', {}))
    return output(dict(request, angle=0.))


if __name__ == '__main__':
    shared.frame_camera = frame_camera
    shared.render = render
    shared.main()
