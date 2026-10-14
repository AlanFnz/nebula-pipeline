"""Independent optical background and an antialiased, centered 3D solid.

The die is ray-cast from geometry, including surface-attached face markings.
Color emulsion remains a shared downstream finish, not a baked-in texture.
"""
import math

import numpy as np

from synth_canvas import content_size, object_offset
from synth_prismatic import _cloud, _colors


PALETTES = ('Optical green / violet', 'Warm film / rose', 'Silver / ink')


def hidden_controls(ranges):
    """Keep both inspectors aligned; mixed/animated choices expose all controls."""
    hidden = set()
    if ranges['solid.shape'][0] == ranges['solid.shape'][1] and ranges['solid.shape'][0] != 0:
        hidden.update(('pip_size', 'pip_light', 'pip_depth'))
    shape = tuple(ranges['solid.shape'])
    if shape == (2, 2): hidden.add('corner_radius')
    elif shape[0] == shape[1]: hidden.update(('model_data', 'height_stretch'))
    material = tuple(ranges['solid.material'])
    if material == (0, 0):
        hidden.update(('roughness', 'specular', 'pip_depth'))
    elif material in ((1, 1), (2, 2)):
        hidden.update(('palette', 'color_phase', 'color_speed', 'wash', 'saturation'))
    if material[0] == material[1] and material[0] != 2:
        hidden.update(('glass_transmission', 'glass_refraction'))
    if material == (2, 2): hidden.update(('pip_size', 'pip_light', 'pip_depth', 'shading'))
    return {'solid.' + key for key in hidden}


def modules(Module, P):
    return (
        Module('color_field', 'Color field',
               'Moving optical color clouds behind generated objects. Remains visible with No object.', (
            P('palette', 'Palette', 0, 0, 2, 1, choices=PALETTES),
            P('color_phase', 'Color phase', .02, 0, 1, .01),
            P('color_speed', 'Color drift', .09, 0, 1, .01),
            P('wash', 'Color clouds', .85, 0, 1, .01),
            P('scale', 'Cloud size', 1., .2, 4, .01, 'Larger values make broader patches.'),
            P('flow', 'Cloud motion', .43, 0, 2, .01),
            P('saturation', 'Saturation', 1., 0, 1.5, .01),
            P('light', 'Exposure', 1., 0, 2, .01),
            P('mix', 'Mix', 1., 0, 1, .01),
        )),
        Module('solid', '3D solid', 'A rotating die, cube or imported static 3D model. Treatments apply to the object and background together.', (
            P('shape', 'Shape', 0, 0, 2, 1, choices=('Die', 'Cube', 'Imported model')),
            P('scale', 'Size', .48, .05, 2, .01, 'Side length relative to the artwork reference. Canvas resizing never stretches the solid.'),
            P('yaw', 'Starting turn', 30., -180, 180, 1),
            P('pitch', 'Starting tilt', -22., -180, 180, 1),
            P('roll', 'Starting roll', 8., -180, 180, 1),
            P('turn_speed', 'Turn speed', 24., -120, 120, .5),
            P('tumble_speed', 'Tumble speed', 7., -120, 120, .5),
            P('roll_speed', 'Roll speed', 3., -120, 120, .5),
            P('variation', 'Turn variation', .45, 0, 1, .01, 'Gently accelerate and slow the rotation without reversing it.'),
            P('perspective', 'Perspective', .7, 0, 1, .01, 'Zero uses parallel projection; larger values deepen perspective.'),
            P('pip_size', 'Dot size', .073, .025, .14, .001),
            P('pip_light', 'Dot brightness', .14, 0, 1, .01),
            P('palette', 'Palette', 0, 0, 2, 1, choices=PALETTES),
            P('color_phase', 'Color phase', .48, 0, 1, .01),
            P('color_speed', 'Color drift', .09, 0, 1, .01),
            P('wash', 'Surface clouds', .55, 0, 1, .01),
            P('shading', 'Face shading', .7, 0, 1, .01),
            P('saturation', 'Saturation', 1., 0, 1.5, .01),
            P('light', 'Exposure', 1.1, 0, 2, .01),
            P('mix', 'Opacity', 1., 0, 1, .01),
            # Append controls so older definitions retain their parameter order.
            P('corner_radius', 'Corner radius', 0., 0, .22, .005, 'Round the actual edges and corners. Radius relative to the side length.'),
            P('material', 'Material', 0, 0, 2, 1, choices=('Optical color', 'White plastic', 'Black glass')),
            P('roughness', 'Surface roughness', .32, .08, 1., .01, 'Low values make tighter reflections; high values give a matte finish. White plastic and Black glass.'),
            P('specular', 'Reflection strength', .5, 0, 1, .01, 'Strength of studio reflections on White plastic or Black glass.'),
            P('pip_depth', 'Dot recess', 0., 0, .04, .001, 'Shallow shading inside the dots. White plastic only; does not change the outer silhouette.'),
            P('model_data', '3D model', '', kind='mesh', hint='Import static GLB/glTF geometry. Embedded in the project; uses the studio material. Up to 60,000 triangles. Set Shape to Imported model.'),
            P('height_stretch', 'Model height', 1., .2, 3., .01, 'Stretch the imported model along its own vertical axis, keeping its width and depth unchanged.'),
            P('glass_transmission', 'Glass transmission', .1, 0, .6, .01, 'How much background shows through the dark glass. Zero makes it opaque.'),
            P('glass_refraction', 'Glass refraction', .18, 0, .6, .01, 'Screen-space distortion of the background inside the glass.'),
        )),
    )


def _grade(image, p):
    luma=image.mean(axis=-1,keepdims=True)
    return np.asarray((luma+(image-luma)*p['saturation'])*p['light'],np.float32)


def render_color_field(arr, p, seconds, preset):
    if not p['mix']: return arr
    h,w=arr.shape[:2]; unit=min(content_size(preset,(w,h)))
    yy,xx=np.mgrid[:h,:w].astype(np.float32)
    # Canvas background deliberately ignores the object's position and rotation.
    x=(xx-w*.5)/unit; y=(yy-h*.5)/unit
    t=seconds*preset['speed']; seed=int(preset['seed'])
    cloud=(.19*_cloud(x*2.1/p['scale'],y*2.1/p['scale'],t*p['flow'],seed)+
           .075*_cloud(x*4.7/p['scale'],y*4.7/p['scale'],t*p['flow']*.31/.43,seed+917))*p['wash']
    field=_colors(p['color_phase']+t*p['color_speed']+x*.045+y*.07+cloud,p['palette'])
    return np.asarray(arr*(1-p['mix'])+_grade(field,p)*p['mix'],np.float32)


def solid_frame(p, size, seconds, preset):
    w,h=size; dx,dy=object_offset(preset,size)
    t=seconds*preset['speed']
    clock=t+p['variation']*(.18*math.sin(t*.8)+.09*math.sin(t*1.7))
    yaw,pitch,roll=np.deg2rad((p['yaw']+clock*p['turn_speed'],
                             p['pitch']+clock*p['tumble_speed'],
                             p['roll']+clock*p['roll_speed']))
    cy,sy=math.cos(yaw),math.sin(yaw); cx,sx=math.cos(pitch),math.sin(pitch); cz,sz=math.cos(roll),math.sin(roll)
    rx=np.array(((1,0,0),(0,cx,-sx),(0,sx,cx)),np.float32)
    ry=np.array(((cy,0,sy),(0,1,0),(-sy,0,cy)),np.float32)
    rz=np.array(((cz,-sz,0),(sz,cz,0),(0,0,1)),np.float32)
    return (w*.5+dx,h*.5+dy),min(content_size(preset,size))*p['scale'],rz@ry@rx


# Opposite faces sum to seven. Coordinates belong to the solid, not the screen.
FACE_VALUES=(1,6,2,5,3,4)
PIPS={
    1: ((0.,0.),),
    2: ((-.24,-.24),(.24,.24)),
    3: ((-.24,-.24),(0.,0.),(.24,.24)),
    4: ((-.24,-.24),(-.24,.24),(.24,-.24),(.24,.24)),
    5: ((-.24,-.24),(-.24,.24),(0.,0.),(.24,-.24),(.24,.24)),
    6: tuple((u,v) for u in (-.24,.24) for v in (-.26,0.,.26)),
}
NORMALS=np.array(((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)),np.float32)


def _surface(local, face, rotation, p, t, seed):
    axis=face//2
    u=np.where(axis==0,local[:,2],local[:,0])
    v=np.where(axis==1,local[:,2],local[:,1])
    cloud=_cloud(u*2.8+face*2.1,v*2.8,t*.22,seed+101)*p['wash']*.10
    coordinate=p['color_phase']+t*p['color_speed']+face*.025+u*.065+v*.04+cloud
    color=_colors(coordinate,p['palette'])
    light=np.array((-.45,.65,1.),np.float32);light/=np.linalg.norm(light)
    diffuse=np.maximum(0.,(NORMALS@rotation.T)@light)
    color*=1-p['shading']*(.5-.5*diffuse[face,None])
    if p['shape']==0:
        for face_id,value in enumerate(FACE_VALUES):
            selected=face==face_id
            if not selected.any(): continue
            distances=np.minimum.reduce([(u[selected]-pu)**2+(v[selected]-pv)**2 for pu,pv in PIPS[value]])
            color[selected]*=np.where(distances<p['pip_size']**2,p['pip_light'],1.)[:,None]
    return _grade(color,p)


def _rounded_hits(origin, direction, near, far, radius):
    """Intersect a rounded box inside its unchanged unit-cube bounds.

    Trace only unresolved rays, including tangencies. The tolerance is in object
    space so canvas reframing cannot change the intersection or its normals.
    """
    distance = near.copy()
    active = np.arange(len(near))
    found = np.zeros(len(near), dtype=bool)
    lengths = np.linalg.norm(direction, axis=1)
    for _ in range(96):
        if not len(active): break
        point = origin[active] + distance[active, None] * direction[active]
        q = np.abs(point) - (.5 - radius)
        sdf = np.linalg.norm(np.maximum(q, 0.), axis=1) + np.minimum(q.max(axis=1), 0.) - radius
        arrived = sdf <= 2e-6
        found[active[arrived]] = True
        pending = active[~arrived]
        distance[pending] += np.maximum(sdf[~arrived], 1e-6) / lengths[pending]
        active = pending[distance[pending] <= far[pending] + 2e-6]
    local = origin[found] + distance[found, None] * direction[found]
    normal = np.sign(local) * np.maximum(np.abs(local) - (.5 - radius), 0.)
    normal /= np.maximum(np.linalg.norm(normal, axis=1, keepdims=True), 1e-8)
    return found, local, normal


def _plastic_surface(local, normal, face, rotation, direction, p):
    """White dielectric with broad studio lights and shallow recessed pip normals.

    Lighting stays in world space while the solid turns. Linear-light diffuse,
    Fresnel highlights and a darker pip cavity are converted to display RGB
    before the common film/CRT treatments.
    """
    axis = face // 2
    u_axis = np.where(axis == 0, 2, 0)
    v_axis = np.where(axis == 1, 2, 1)
    rows = np.arange(len(local))
    u, v = local[rows, u_axis], local[rows, v_axis]
    dots = np.zeros(len(local), dtype=bool)
    cavity = np.ones(len(local), dtype=np.float32)
    normal = normal.copy()
    if p['shape'] == 0:
        radius = p['pip_size']
        for face_id, value in enumerate(FACE_VALUES):
            # Pips belong to the flat face, never to a rounded edge.
            selected = (face == face_id) & (np.abs(normal[rows, axis]) > .999)
            for pu, pv in PIPS[value]:
                du, dv = u - pu, v - pv
                r2 = (du*du + dv*dv) / (radius*radius)
                inside = selected & (r2 < 1.)
                dots |= inside
                gradient = 4 * p.get('pip_depth', 0.) / (radius*radius) * (1-r2[inside])
                ids = rows[inside]
                normal[ids, u_axis[inside]] -= gradient * du[inside]
                normal[ids, v_axis[inside]] -= gradient * dv[inside]
                cavity[inside] = 1 - .35 * min(1., p.get('pip_depth', 0.)/.02) * (1-r2[inside])
    normal /= np.maximum(np.linalg.norm(normal, axis=1, keepdims=True), 1e-8)
    normal = normal @ rotation.T
    view = -direction @ rotation.T
    view /= np.linalg.norm(view, axis=1, keepdims=True)
    base = np.full((len(local), 3), .88, np.float32)
    base[dots] = p['pip_light'] ** 2.2
    ambient = (.16 + .10 * (normal[:, 1] + 1.) * .5)[:, None]
    diffuse = ambient.copy()
    reflection = np.zeros_like(base)
    roughness = p.get('roughness', .32)
    exponent = 2. / max(.08, roughness)**2
    for vector, strength, tint in (((-.65,.85,1.2), .62, (1.,.97,.93)),
                                   ((.9,.25,.55), .24, (.88,.94,1.))):
        light = np.array(vector, np.float32); light /= np.linalg.norm(light)
        ndotl = np.maximum(0., normal @ light)
        diffuse += (strength * ndotl)[:, None]
        half = view + light
        half /= np.linalg.norm(half, axis=1, keepdims=True)
        fresnel = .04 + .96 * (1-np.clip(np.sum(view*half, axis=1),0,1))**5
        highlight = np.maximum(0., np.sum(normal*half, axis=1)) ** exponent
        # Broad area-light response; black pigment retains a weaker reflection.
        reflection += (highlight * fresnel * (exponent+2.)/8. * strength * ndotl)[:,None] * np.array(tint)
    lit = base * ((1-p['shading']) + p['shading']*diffuse) * cavity[:,None]
    lit += reflection * p.get('specular', .5) * np.where(dots,.35,1.)[:,None]
    return _grade(np.maximum(lit,0.)**(1/2.2),p)


def render_solid(arr,p,seconds,preset):
    if not p['mix']: return arr
    if p['shape'] == 2:
        from synth_mesh_render import render_mesh
        return render_mesh(arr,p,seconds,preset)
    h,w=arr.shape[:2]; (cx,cy),unit,rotation=solid_frame(p,(w,h),seconds,preset)
    # The projected bounding sphere encloses every orientation even at maximum
    # perspective. Crop work, not the model, to the canvas.
    radius=unit*.90+2
    left,right=max(0,math.floor(cx-radius)),min(w,math.ceil(cx+radius))
    top,bottom=max(0,math.floor(cy-radius)),min(h,math.ceil(cy+radius))
    if left>=right or top>=bottom: return arr
    result=arr.copy(); perspective=p['perspective']; width=right-left
    xs=left+(np.arange(width*2,dtype=np.float32)+.5)*.5-.5
    t=seconds*preset['speed']
    # Two samples per axis; bounded tiles avoid huge export-size intermediates.
    for start in range(top,bottom,48):
        end=min(bottom,start+48)
        ys=start+(np.arange((end-start)*2,dtype=np.float32)+.5)*.5-.5
        sx,sy=np.meshgrid((xs-cx)/unit,-(ys-cy)/unit)
        origin=np.stack((sx*(1-perspective),sy*(1-perspective),np.full_like(sx,4.)),axis=-1)@rotation
        direction=np.stack((sx*perspective/4,sy*perspective/4,-np.ones_like(sx)),axis=-1)@rotation
        divisor=np.where(np.abs(direction)>1e-7,direction,np.where(direction<0,-1e-7,1e-7))
        a=(-.5-origin)/divisor; b=(.5-origin)/divisor
        near=np.minimum(a,b).max(axis=-1);far=np.maximum(a,b).min(axis=-1)
        hit=(far>=near)&(near>0)
        tile=np.repeat(np.repeat(arr[start:end,left:right],2,axis=0),2,axis=1)
        if hit.any():
            local=origin[hit]+near[hit,None]*direction[hit]
            normals = None
            if p.get('corner_radius', 0.) > 0.:
                rounded, local, normals = _rounded_hits(origin[hit], direction[hit], near[hit], far[hit], p['corner_radius'])
                hit[hit] = rounded
            axis=np.abs(local).argmax(axis=-1)
            face=axis*2+(local[np.arange(len(local)),axis]<0)
            if p.get('material', 0) == 2:
                from synth_glass import glass_surface
                hy,hx=np.nonzero(hit)
                surface=glass_surface(NORMALS[face] if normals is None else normals,rotation,direction[hit],p,
                                      arr,xs[hx],ys[hy],unit,local)
            elif p.get('material', 0) == 1:
                surface = _plastic_surface(local, NORMALS[face] if normals is None else normals,
                                           face, rotation, direction[hit], p)
            else:
                surface=_surface(local,face,rotation,p,t,int(preset['seed']))
                if normals is not None:
                    light=np.array((-.45,.65,1.),np.float32);light/=np.linalg.norm(light)
                    old=1-p['shading']*(.5-.5*np.maximum(0.,(NORMALS[face]@rotation.T)@light))
                    new=1-p['shading']*(.5-.5*np.maximum(0.,(normals@rotation.T)@light))
                    surface *= (new/old)[:,None]
            tile[hit]=tile[hit]*(1-p['mix'])+surface*p['mix']
        result[start:end,left:right]=tile.reshape(end-start,2,width,2,3).mean(axis=(1,3))
    return result
