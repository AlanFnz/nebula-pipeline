"""Independent part transforms layered over the unchanged v1 scene builder."""
import colorsys
import json
from pathlib import Path
import sys

# The bundled scripts live inside the signed application. Blender must not
# create or refresh bytecode there while loading the original scene builder.
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import scene_worker as base
from mathutils import Matrix, Vector, Euler
import math

# Pivots in each original parent's coordinates. Keep the meshes and their
# normals untouched; neutral settings use their original matrices verbatim.
PARTS = {
    'base': ('Turned foot', (0,0,.81)),
    'upper': ('Upper hoop', (0,0,3.86)),
    'lower': ('Lower hoop', (0,0,2.29)),
    'spindle': ('Central spindle', (0,0,3.10)),
    'crown': ('Crown', (0,0,4.96)),
    'left': ('Axle -1', (-.62,0,3.09)),
    'right': ('Axle 1', (.62,0,3.09)),
}
pieces = {}
original_render = base.render


def remember():
    pieces.clear()
    base.bpy.context.view_layer.update()
    for key,(name,pivot) in PARTS.items():
        obj = base.bpy.data.objects[name]
        pieces[key] = dict(obj=obj, parent=obj.parent, matrix=obj.matrix_basis.copy(),
                           location=obj.location.copy(), rotation=obj.rotation_euler.copy(), scale=obj.scale.copy(),
                           pivot=Vector(pivot), material=obj.data.materials[0], custom=None,
                           carrier=None, dirty=False)
    # Bind matrix excludes the animated assembly turn.
    global rotor_bind
    rotor_bind = base.rotor.matrix_basis.copy()


def apply_parts(poses):
    for key, saved in pieces.items():
        obj = saved['obj']; pose = poses.get(key)
        if not pose:
            if saved['dirty']:
                obj.parent = saved['parent']; obj.location = saved['location']
                obj.rotation_euler = saved['rotation']; obj.scale = saved['scale']
                obj.hide_render = False; obj.data.materials[0] = saved['material']
                saved['dirty'] = False
            continue
        saved['dirty'] = True
        delta = (Matrix.Translation(saved['pivot']+Vector(pose['position'])) @
                 Euler(tuple(math.radians(v) for v in pose['rotation']), 'XYZ').to_matrix().to_4x4() @
                 Matrix.Diagonal((*pose['scale'],1.)) @ Matrix.Translation(-saved['pivot']))
        source = rotor_bind if saved['parent'] else Matrix.Identity(4)
        target = rotor_bind if pose['follow'] else Matrix.Identity(4)
        # Preserve the original assembly stretch in a separate transform.
        # Flattening it into the rotated object would discard shear when the
        # assembly's width and height differ and this piece turns independently.
        if saved['carrier'] is None:
            carrier = base.bpy.data.objects.new('Part frame / '+key, None)
            base.bpy.context.collection.objects.link(carrier)
            saved['carrier'] = carrier
        carrier = saved['carrier']
        carrier.parent = base.rotor if pose['follow'] else None
        carrier.matrix_basis = target.inverted() @ source
        obj.parent = carrier
        obj.matrix_basis = delta @ saved['matrix']
        obj.hide_render = not pose['visible']
        settings = pose.get('material')
        if settings is None:
            obj.data.materials[0] = saved['material']
        else:
            if saved['custom'] is None: saved['custom'] = saved['material'].copy()
            mat = saved['custom']; obj.data.materials[0] = mat
            shader = mat.node_tree.nodes.get('Principled BSDF')
            color = colorsys.hsv_to_rgb(settings['hue'], settings['saturation'], .82)
            shader.inputs['Base Color'].default_value = (*base.linear(color),1.)
            shader.inputs['Metallic'].default_value = settings['metallic']
            shader.inputs['Roughness'].default_value = settings['roughness']


def render(request):
    key = json.dumps(request['params'], sort_keys=True)
    if key != base.scene_key:
        base.build(request['params']); base.configure_device(); base.scene_key = key
        remember()
    apply_parts(request.get('parts', {}))
    return original_render(request)


base.render = render
if __name__ == '__main__': base.main()
