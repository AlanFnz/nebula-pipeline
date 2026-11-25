"""Optional center geometry for the suspended assembly's existing hub axis."""
import math
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

import bpy
from mathutils import Vector
import suspended_rings as rings


def infinity_mesh(radius, stroke, bow):
    # A closed lemniscate in XZ. Its two passes through the origin run at
    # opposite depths, leaving a physical gap even at the minimum crossing lift.
    stroke = min(stroke, radius * .20)
    span = radius - stroke
    height = span * .39
    lift = 1.25 * stroke + bow * radius
    sections, sides = 192, 32
    vertices, faces = [], []
    for i in range(sections):
        t = math.tau * i / sections
        center = Vector((span*math.sin(t), lift*math.cos(t), height*math.sin(2*t)))
        tangent = Vector((span*math.cos(t), -lift*math.sin(t), 2*height*math.cos(2*t))).normalized()
        across = Vector((-tangent.z, 0., tangent.x)).normalized()
        normal = tangent.cross(across)
        row, next_row = i*sides, ((i+1) % sections)*sides
        for j in range(sides):
            angle = math.tau * j / sides
            vertices.append(center + across*(stroke*math.cos(angle)) + normal*(.85*stroke*math.sin(angle)))
            k = (j+1) % sides
            faces.append((row+j, row+k, next_row+k, next_row+j))
    mesh = bpy.data.meshes.new('Infinity loop')
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    return mesh


build_rings = rings.build


def build(params):
    build_rings(params)
    disc, axis = rings.pieces['core']
    mesh = infinity_mesh(params['core_size'], params['tube_radius'], params['hoop_bow'])
    loop = bpy.data.objects.new('Infinity loop', mesh)
    bpy.context.collection.objects.link(loop)
    rings.shared.attach(loop, disc.data.materials[0], axis)
    rings.pieces['core'] = (loop, axis)
    bpy.data.objects.remove(disc, do_unlink=True)


if __name__ == '__main__':
    rings.build = build
    rings.shared.frame_camera = rings.frame_camera
    rings.shared.render = rings.render
    rings.shared.main()
