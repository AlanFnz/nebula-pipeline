"""Shared Optical relic studio. Geometry and choreography belong to each source."""
import colorsys
import math
import bpy
from scene_worker import material, linear, attach, area


def environment(p):
    scene = bpy.context.scene
    scene.world.use_nodes = True
    scene.world.node_tree.nodes.clear()
    world = scene.world.node_tree.nodes.new('ShaderNodeBackground')
    output = scene.world.node_tree.nodes.new('ShaderNodeOutputWorld')
    scene.world.node_tree.links.new(world.outputs[0],output.inputs['Surface'])
    world.inputs[0].default_value = (.62, .72, .58, 1)
    world.inputs[1].default_value = p.get('environment', .07)
    nodes=scene.world.node_tree.nodes; links=scene.world.node_tree.links
    # A studio environment with a dark upper-right flag supplies the broad
    # angular reflections visible on all three rounded masses in the reference.
    # It is lighting in 3D: reflections follow the surface as it rotates.
    direction=nodes.new('ShaderNodeTexCoord'); axes=nodes.new('ShaderNodeSeparateXYZ')
    links.new(direction.outputs['Normal'],axes.inputs[0])
    right=nodes.new('ShaderNodeMath'); right.operation='LESS_THAN'; right.inputs[1].default_value=-.12
    upper=nodes.new('ShaderNodeMath'); upper.operation='LESS_THAN'; upper.inputs[1].default_value=-.18
    links.new(axes.outputs['X'],right.inputs[0]); links.new(axes.outputs['Z'],upper.inputs[0])
    mask=nodes.new('ShaderNodeMath'); mask.operation='MULTIPLY'
    links.new(right.outputs[0],mask.inputs[0]); links.new(upper.outputs[0],mask.inputs[1])
    strength=nodes.new('ShaderNodeMath'); strength.operation='MULTIPLY'; strength.inputs[1].default_value=min(1.,p.get('reflection_contrast',1.))
    links.new(mask.outputs[0],strength.inputs[0])
    color=nodes.new('ShaderNodeMixRGB'); color.inputs[1].default_value=(.58,.76,.54,1.); color.inputs[2].default_value=(.012,.045,.025,1.)
    links.new(strength.outputs[0],color.inputs[0]); links.new(color.outputs[0],world.inputs[0])
    floor_color = colorsys.hsv_to_rgb(p['background_hue'], p['background_saturation'], .48)
    floor = material('Green seamless', linear(floor_color), rough=.7)
    floor_shader = floor.node_tree.nodes.get('Principled BSDF')
    floor_shader.inputs['Emission Color'].default_value = (*linear(floor_color),1.)
    floor_shader.inputs['Emission Strength'].default_value = .6
    # A photographic backdrop lift must not become a giant luminous reflector
    # on the metal. Preserve the key's contact shading in the camera image.
    ray = floor.node_tree.nodes.new('ShaderNodeLightPath')
    lift = floor.node_tree.nodes.new('ShaderNodeMath'); lift.operation = 'MULTIPLY'
    lift.inputs[1].default_value = .12
    floor.node_tree.links.new(ray.outputs['Is Camera Ray'],lift.inputs[0])
    floor.node_tree.links.new(lift.outputs[0],floor_shader.inputs['Emission Strength'])
    tint = colorsys.hsv_to_rgb(p['metal_hue'], p['metal_saturation'], .82)
    metal = material('Satin alloy', linear(tint), p['metallic'], p['roughness'])
    profile = [(-25.,0.),(1.5,0.)]
    profile += [(1.5+3*math.sin(i*math.pi/48),3*(1-math.cos(i*math.pi/48))) for i in range(1,25)]
    profile += [(4.5,25.)]
    mesh = bpy.data.meshes.new('Cyclorama')
    vertices = [(x,y,z) for y,z in profile for x in (-30.,30.)]
    mesh.from_pydata(vertices,[],[(2*i,2*i+1,2*i+3,2*i+2) for i in range(len(profile)-1)])
    mesh.update(); ground=bpy.data.objects.new('Seamless floor',mesh)
    bpy.context.collection.objects.link(ground); attach(ground,floor)
    ground.visible_glossy = False
    return metal


def lights(p):
    angle = math.radians(p['light_angle'])
    area('Key softbox', (5*math.sin(angle),-5*math.cos(angle),7.5), p['light_power'], p['light_size'], (1.,.91,.74),(0,0,2.8))
    area('Green fill', (3,1,4), p['light_power']*.12, 5., (.54,1.,.79),(0,0,2.6))
    area('Top reflection', (-1,3,7),p['light_power']*.25, 3., (.82,1.,.86),(0,0,3))
