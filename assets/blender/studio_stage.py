"""Shared Optical relic studio. Geometry and choreography belong to each source."""
import colorsys
import math
import bpy
from mathutils import Vector
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
    floor_color = colorsys.hsv_to_rgb(p['background_hue'], p['background_saturation'], p.get('background_light', .48))
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
    tint = colorsys.hsv_to_rgb(p['metal_hue'], p['metal_saturation'], p.get('metal_light', .82))
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


def _native_vertices(obj):
    """Always fit from authored geometry, including after a larger request."""
    key = '_nebula_stage_vertices'
    if key not in obj:
        obj[key] = [component for vertex in obj.data.vertices for component in vertex.co]
    values = obj[key]
    return [Vector(values[i:i+3]) for i in range(0,len(values),3)]


def fit_to_camera(scene):
    """Keep the orthographic viewport inside a physical floor and backdrop.

    A larger canvas widens the parallel ray bundle. Its bottom rays used to
    start below the floor (or behind the wall), exposing the lighting world.
    Retreat along the optical axis: framing and object scale do not change.
    Extend only outer stage edges that the new viewport can actually reach.
    The original camera and meshes remain exact for authored study canvases.
    """
    camera = scene.camera
    if camera.data.type != 'ORTHO': return
    seamless = bpy.data.objects.get('Seamless floor')
    floor = seamless if seamless is not None else bpy.data.objects.get('Ground')
    wall = bpy.data.objects.get('Sky')
    if floor is None: return
    wall_y = 4.5 if seamless is not None else wall.location.y
    if '_nebula_stage_camera' not in camera:
        camera['_nebula_stage_camera'] = list(camera.location)
        camera['_nebula_stage_clip'] = camera.data.clip_end
    original = Vector(camera['_nebula_stage_camera'])
    orientation = camera.rotation_euler.to_quaternion()
    back = orientation @ Vector((0,0,1))
    offsets = [orientation @ Vector((v.x,v.y,0)) for v in camera.data.view_frame(scene=scene)]
    retreat = max(0., (original.y+max(v.y for v in offsets)-wall_y+.25)/max(1e-6,-back.y))
    if back.z > 1e-5:
        retreat = max(retreat, (.25-original.z-min(v.z for v in offsets))/back.z)
    camera.location = original+back*retreat
    origins = [camera.location+v for v in offsets]
    direction = -back
    wall_hits = [o+direction*((wall_y-o.y)/direction.y) for o in origins]
    ground_hits = [o+direction*(-o.z/direction.z) for o in origins] if back.z > 1e-5 else []
    hits = wall_hits+ground_hits
    camera.data.clip_end = max(camera['_nebula_stage_clip'],
        max((v-camera.location).length for v in hits)+10.)
    width = max(abs(v.x) for v in hits)+2.
    height = max(v.z for v in wall_hits)+2.
    front = min((v.y for v in ground_hits),default=-25.)-2.
    if seamless is not None:
        for vertex, native in zip(floor.data.vertices,_native_vertices(floor)):
            native.x = math.copysign(max(30.,width),native.x)
            if native.y == -25.: native.y = min(-25.,front)
            if native.z == 25.: native.z = max(25.,height)
            vertex.co = native
    else:
        for vertex, native in zip(floor.data.vertices,_native_vertices(floor)):
            native.x = math.copysign(max(100.,width),native.x)
            if native.y < 0.: native.y = min(-100.,front)
            vertex.co = native
        for vertex, native in zip(wall.data.vertices,_native_vertices(wall)):
            native.x = math.copysign(max(100.,width),native.x)
            if native.y > 0.: native.y = max(100.,height-100.)
            vertex.co = native
        wall.data.update()
    floor.data.update()
    # At exactly zero elevation parallel rays cannot meet the horizontal
    # ground. Close the stage below it with the same ground material instead
    # of letting these rays see the unrelated reflection environment.
    lower = min(v.z for v in wall_hits)
    skirt = bpy.data.objects.get('Stage lower wall')
    if lower < 0.:
        if skirt is None:
            mesh = bpy.data.meshes.new('Stage lower wall')
            mesh.from_pydata([(0,0,0)]*4,[],[(0,1,2,3)])
            skirt = bpy.data.objects.new('Stage lower wall',mesh)
            bpy.context.collection.objects.link(skirt)
            attach(skirt,floor.data.materials[0])
            skirt.visible_glossy = floor.visible_glossy
        span = max(30.,width)
        for vertex,co in zip(skirt.data.vertices,
                [(-span,wall_y,lower-2.),(span,wall_y,lower-2.),(span,wall_y,0.),(-span,wall_y,0.)]):
            vertex.co = co
        skirt.data.update()
        skirt.hide_render = False
    elif skirt is not None:
        skirt.hide_render = True
