"""Independent optical background and an antialiased, centered 3D solid.

The die is ray-cast from geometry, including surface-attached face markings.
Color emulsion remains a shared downstream finish, not a baked-in texture.
"""
import math

import numpy as np

from synth_canvas import content_size, object_offset
from synth_prismatic import _cloud, _colors


PALETTES = ('Optical green / violet', 'Warm film / rose', 'Silver / ink')


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
        Module('solid', '3D solid', 'A rotating die or unmarked cube. Treatments apply to the object and background together.', (
            P('shape', 'Shape', 0, 0, 1, 1, choices=('Die', 'Cube')),
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


def render_solid(arr,p,seconds,preset):
    if not p['mix']: return arr
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
            axis=np.abs(local).argmax(axis=-1)
            face=axis*2+(local[np.arange(len(local)),axis]<0)
            surface=_surface(local,face,rotation,p,t,int(preset['seed']))
            tile[hit]=tile[hit]*(1-p['mix'])+surface*p['mix']
        result[start:end,left:right]=tile.reshape(end-start,2,width,2,3).mean(axis=(1,3))
    return result
