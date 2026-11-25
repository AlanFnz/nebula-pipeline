"""A finite studio light tent. Its colored cards are reflected by real surfaces."""
import colorsys
import math

import bpy
import numpy as np
from mathutils import Vector

import scene_worker as shared


def color(p, prefix):
    # Neutral brightness settings are elided by the shared worker protocol.
    light = p.get(prefix + '_light', .82 if prefix == 'metal' else .48)
    return np.asarray(colorsys.hsv_to_rgb(p[prefix+'_hue'], p[prefix+'_saturation'], light))


def light_cards(p):
    """Build a seamless latitude/longitude light rig in display RGB, then linearize it."""
    w, h = 1024, 512
    lon = ((np.arange(w) + .5) / w - .5)[None, :] * math.tau
    lat = ((np.arange(h) + .5) / h - .5)[:, None] * math.pi
    key = color(p, 'accent')
    warm = color(p, 'reflection')
    second = np.array(colorsys.hsv_to_rgb((p['reflection_hue'] + p['reflection_spread']) % 1,
                                          p['reflection_saturation'] * .66, p['reflection_light']))
    hue, sat, value = colorsys.rgb_to_hsv(*key)
    blue = np.array(colorsys.hsv_to_rgb((hue + .04) % 1, min(1, sat + .65), value * .9))
    aqua = np.array(colorsys.hsv_to_rgb((hue - .12) % 1, min(1, sat + .46), value * .70))
    room = np.empty((h, w, 3))
    room[:] = aqua * (.42 + .30 * (1 - p['reflection_contrast']))
    softness = .034 + .018 * p['light_size']

    def feather(distance):
        t = np.clip(.5 + distance / softness, 0., 1.)
        return t * t * (3 - 2*t)

    def panel(mask, tint):
        alpha = mask[..., None]
        room[:] = room * (1 - alpha) + tint * alpha

    # A broad diffuser opposite the lens and narrow banks around the sides and
    # back. Curved reflections on bevels sample the same rig as the flat faces.
    panel(feather(.66 - abs(lat + .10*np.cos(2*lon))) *
          (.32 + .22*np.cos(3*lon + 1.0)), aqua)
    ribbon = lat - .46*np.sin(2*lon) - .22*np.sin(5*lon + .7)
    for level, width, tint in ((-.60,.13,blue),(-.34,.055,warm*.82),(-.12,.036,key*.76),
                               (.10,.17,blue),(.40,.049,warm*.9),(.60,.15,aqua)):
        panel(feather(width - abs(ribbon - level)), tint)
    for center, width, tint in ((-1.55,.085,blue),(1.70,.085,warm*.81),(2.80,.15,blue),(-2.65,.04,second)):
        delta = np.arctan2(np.sin(lon-center), np.cos(lon-center))
        panel(feather(width - abs(delta + .12*np.sin(lat*4))) * feather(.95-abs(lat)), tint)

    front = feather(1.40 - abs(lon + .17*np.sin(lat*4))) * feather(.67 - abs(lat))
    height = lat + .60*np.sin(lon) - .14*(1-np.cos(2*lon))
    face = key * (.93 + .065*np.sin(5*height))[...,None]
    panel(front, face)
    panel(front * feather(.100 - abs(height-.35)), warm)
    panel(front * feather(.049 - abs(height+.30)), second)
    panel(front * feather(.095 - abs(height+.51)), warm * .79)
    for center in (-.63, .67):
        spot = np.exp(-((lon-center)/.10)**2 - ((lat-.08*np.sin(3*center))/.13)**2)
        panel(spot, np.array((1.,1.,1.)))
    # A second bank behind the sculpture provides transmitted light through
    # glass. Back and side walls have different exposures as in a real light tent.
    rear_lon = np.arctan2(-np.sin(lon), -np.cos(lon))
    rear = feather(1.05 - abs(rear_lon)) * feather(.79 - abs(lat))
    rise = lat + .30*np.sin(rear_lon) + .05*np.sin(2*rear_lon)
    panel(rear, key * (.96+.06*np.sin(4*rise))[...,None])
    panel(rear*feather(.116-abs(rise-.37)), warm)
    panel(rear*feather(.048-abs(rise+.31)), second)
    panel(rear*feather(.075-abs(rise+.55)), warm*.78)
    rgb = np.clip(room, 0, 1)
    linear = np.where(rgb <= .04045, rgb / 12.92, ((rgb+.055)/1.055)**2.4)
    # Small, bright sources stay visible inside refracted paths and in the
    # rounded rims. Retain their radiance above display white until camera exposure.
    lime = np.array(colorsys.hsv_to_rgb((p['reflection_hue']+.055)%1, .91, 1.))
    for az, el, width, height, tint, power in (
        (-1.16,.22,.065,.45,lime,2.8), (1.24,-.06,.07,.34,lime,2.4),
        (.48,-.13,.055,.085,key,3.7), (-.78,.38,.08,.11,key,4.0),
        (2.55,.52,.11,.38,lime,2.7), (-2.12,-.28,.08,.20,blue,3.5),
        (.18,1.15,.18,.14,key,3.6), (-.32,-1.08,.16,.14,key,3.0)):
        delta = np.arctan2(np.sin(lon-az),np.cos(lon-az))
        spot = np.exp(-.5*((delta/width)**2+((lat-el)/height)**2))
        linear += spot[...,None]*np.asarray(shared.linear(tint))*power
    pixels = np.ones((h, w, 4), dtype=np.float32)
    pixels[:,:,:3] = linear
    image = bpy.data.images.new('Studio reflection cards', w, h, float_buffer=True)
    image.colorspace_settings.name = 'Non-Color'
    image.pixels.foreach_set(pixels.ravel())
    image.update()
    return image


def emission(name):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    shader = nodes.new('ShaderNodeEmission')
    links.new(shader.outputs[0], nodes.new('ShaderNodeOutputMaterial').inputs['Surface'])
    return mat, nodes, links, shader


def coat_material(mat, amount):
    """Angular transmission relative to the polished plate, including its rim."""
    if not amount:
        return
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    transform = nodes.new('ShaderNodeVectorTransform')
    transform.vector_type = 'VECTOR'
    transform.convert_from, transform.convert_to = 'WORLD', 'OBJECT'
    links.new(nodes.new('ShaderNodeNewGeometry').outputs['Incoming'], transform.inputs[0])
    normal = nodes.new('ShaderNodeVectorMath')
    normal.operation = 'NORMALIZE'
    links.new(transform.outputs[0], normal.inputs[0])
    axes = nodes.new('ShaderNodeSeparateXYZ')
    links.new(normal.outputs[0], axes.inputs[0])
    absolute = nodes.new('ShaderNodeMath')
    absolute.operation = 'ABSOLUTE'
    links.new(axes.outputs['Y'], absolute.inputs[0])
    power = nodes.new('ShaderNodeMath')
    power.operation = 'POWER'
    links.new(absolute.outputs[0], power.inputs[0])
    power.inputs[1].default_value = 8.
    strength = nodes.new('ShaderNodeMath')
    strength.operation = 'MULTIPLY'
    strength.inputs[1].default_value = amount
    links.new(power.outputs[0], strength.inputs[0])
    mix = nodes.new('ShaderNodeMixRGB')
    mix.name = 'Angle tint'
    links.new(strength.outputs[0], mix.inputs[0])
    links.new(mix.outputs[0], nodes['Principled BSDF'].inputs['Base Color'])


def tint(mat, rgb):
    shader = mat.node_tree.nodes['Principled BSDF']
    linear = shared.linear(rgb)
    mix = mat.node_tree.nodes.get('Angle tint')
    if mix is not None:
        mix.inputs[1].default_value = (*linear, 1.)
        mix.inputs[2].default_value = (*([max(linear)]*3), 1.)
    else:
        shader.inputs['Base Color'].default_value = (*linear, 1.)


def surface_texture(mat, amount):
    if not amount:
        return
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 3.2
    noise.inputs['Detail'].default_value = 1.7
    links.new(nodes.new('ShaderNodeTexCoord').outputs['Object'], noise.inputs['Vector'])
    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = amount
    bump.inputs['Distance'].default_value = .045
    links.new(noise.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], nodes['Principled BSDF'].inputs['Normal'])


def build(p):
    # Custom UVs place the center of the front diffuser on the negative Y axis.
    cols, rows = 96, 48
    radius = 4.15
    vertices, faces = [], []
    for j in range(rows+1):
        lat = (j/rows - .5)*math.pi
        for i in range(cols+1):
            lon = (i/cols - .5)*math.tau
            vertices.append((radius*math.cos(lat)*math.sin(lon), -radius*math.cos(lat)*math.cos(lon),
                             radius*math.sin(lat)))
            if i < cols and j < rows:
                k = j*(cols+1)+i
                faces.append((k,k+1,k+cols+2,k+cols+1))
    mesh = bpy.data.meshes.new('Studio light tent')
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    uv = mesh.uv_layers.new()
    for loop in mesh.loops:
        j, i = divmod(loop.vertex_index, cols+1)
        uv.data[loop.index].uv = (i/cols, j/rows)
    dome = bpy.data.objects.new(mesh.name, mesh)
    bpy.context.collection.objects.link(dome)
    mat, nodes, links, shader = emission('Studio cards')
    texture = nodes.new('ShaderNodeTexImage')
    texture.image = light_cards(p)
    links.new(texture.outputs['Color'], shader.inputs['Color'])
    shader.inputs['Strength'].default_value = p['environment'] * p['light_power']/1000.
    shared.attach(dome, mat)
    dome.rotation_euler.z = math.radians(p['light_angle'])
    dome.visible_camera = False
    dome.visible_shadow = False

    mat, nodes, links, shader = emission('Graded backdrop')
    xyz = nodes.new('ShaderNodeSeparateXYZ')
    links.new(nodes.new('ShaderNodeNewGeometry').outputs['Position'], xyz.inputs[0])
    gradient = nodes.new('ShaderNodeMapRange')
    gradient.interpolation_type = 'SMOOTHSTEP'
    gradient.inputs['From Min'].default_value = -2.45
    gradient.inputs['From Max'].default_value = .05
    links.new(xyz.outputs['Z'], gradient.inputs[0])
    mix = nodes.new('ShaderNodeMixRGB')
    mix.inputs[1].default_value = (*shared.linear(color(p,'ground')), 1)
    mix.inputs[2].default_value = (*shared.linear(color(p,'background')), 1)
    links.new(gradient.outputs[0], mix.inputs[0])
    links.new(mix.outputs[0], shader.inputs['Color'])
    # A large, camera-facing backdrop covers the full range of canvas framings.
    camera = bpy.context.scene.camera
    back = camera.rotation_euler.to_matrix() @ Vector((0,0,1))
    bpy.ops.mesh.primitive_plane_add(size=2000, location=-back*6, rotation=camera.rotation_euler)
    wall = bpy.context.object
    shared.attach(wall, mat)
    wall.visible_glossy = wall.visible_diffuse = wall.visible_shadow = False
