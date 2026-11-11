"""Optional orbital shapes and finishes; the original assembly stays intact."""
import colorsys
import math

import bpy
from mathutils import Matrix

import orbital_scene as orbital
import scene_worker as shared
import studio_stage


def tint_symbol(mat, hue, saturation, dark):
    colors = mat.node_tree.nodes['Yin colors']
    colors.inputs[1].default_value = (*shared.linear(colorsys.hsv_to_rgb(hue, saturation, dark)), 1.)
    colors.inputs[2].default_value = (*shared.linear(colorsys.hsv_to_rgb(hue, saturation, .82)), 1.)


def symbol_material(radius, p):
    """An analytic inlay in object coordinates, visible on both physical faces."""
    mat = shared.material('Yin yang alloy', (1., 1., 1.), p['metallic'], p['roughness'])
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    coords = nodes.new('ShaderNodeTexCoord')
    axes = nodes.new('ShaderNodeSeparateXYZ')
    links.new(coords.outputs['Object'], axes.inputs[0])

    def op(operation, a, b):
        node = nodes.new('ShaderNodeMath'); node.operation = operation
        for i, value in enumerate((a, b)):
            if isinstance(value, (float, int)): node.inputs[i].default_value = value
            else: links.new(value, node.inputs[i])
        return node.outputs[0]

    x, z = axes.outputs['X'], axes.outputs['Z']
    x2 = op('MULTIPLY', x, x)

    def circle(center, r):
        dz = op('SUBTRACT', z, center)
        distance2 = op('ADD', x2, op('MULTIPLY', dz, dz))
        return op('LESS_THAN', distance2, r*r)

    # Two semicircles form the S, with an opposite-color eye in each lobe.
    white = op('GREATER_THAN', x, 0.)
    white = op('MAXIMUM', white, circle(radius*.5, radius*.5))
    white = op('MULTIPLY', white, op('SUBTRACT', 1., circle(-radius*.5, radius*.5)))
    white = op('MULTIPLY', white, op('SUBTRACT', 1., circle(radius*.5, radius*p['yin_dot'])))
    white = op('MAXIMUM', white, circle(-radius*.5, radius*p['yin_dot']))
    colors = nodes.new('ShaderNodeMixRGB'); colors.name = 'Yin colors'
    links.new(white, colors.inputs[0])
    links.new(colors.outputs[0], nodes['Principled BSDF'].inputs['Base Color'])
    tint_symbol(mat, p['metal_hue'], p['metal_saturation'], p['yin_darkness'])
    return mat


def apply(p):
    if p.get('orbital_finish', 0):
        # Same cyclorama, reflection flag and softboxes as Optical relic.
        for name in ('Ground', 'Sky', 'Key'):
            bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)
        metal = studio_stage.environment(p)
        studio_stage.lights(p)
        scene = bpy.context.scene
        scene.view_settings.view_transform = 'AgX'
        scene.view_settings.look = 'AgX - Medium High Contrast'
        for name, _ in orbital.PARTS.values():
            obj = bpy.data.objects[name]
            for i in range(len(obj.data.materials)): obj.data.materials[i] = metal

    for i in range(1, 6):
        if not p.get(f'orbit_shape_{i}', 0): continue
        name = f'Orbital ring {i}'
        old = bpy.data.objects[name]; parent = old.parent
        bpy.data.objects.remove(old, do_unlink=True)
        radius = 1.94-(i-1)*min(p['band_width']+p['ring_gap'], .35)
        mat = symbol_material(radius, p)
        obj = orbital.cylinder(name, radius, p['band_depth'], 0., mat,
                               min(p['edge_radius'], p['band_depth']*.45))
        # Keep local XZ coordinates shared by every orbital piece and its editor.
        obj.data.transform(Matrix.Rotation(math.pi/2, 4, 'X'))
        obj.parent = parent

    # Same transform/material editor and authored motion for both shapes.
    for key, (name, _) in orbital.PARTS.items():
        obj = bpy.data.objects[name]
        orbital.bindings[key] = (obj.parent, obj.matrix_basis.copy(), tuple(obj.data.materials), {})
