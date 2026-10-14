"""Deterministic, depth-tested static mesh rasterization shared by preview/export."""
import numpy as np
from synth_mesh import decode_mesh


def _raster_tile(points, world, denominator, vertices, normals, faces, bounds, width, start, stop):
    depth=np.full((stop-start,width),-np.inf,np.float32)
    normal_buffer=np.zeros((stop-start,width,3),np.float32)
    position_buffer=np.zeros_like(normal_buffer)
    candidates=np.flatnonzero((bounds[:,1]<stop)&(bounds[:,3]>=start)&(bounds[:,0]<width)&(bounds[:,2]>=0))
    for index in candidates:
        indices=faces[index];a,b,c=points[indices]
        x0=max(0,int(bounds[index,0]));x1=min(width-1,int(bounds[index,2]))
        y0=max(start,int(bounds[index,1]));y1=min(stop-1,int(bounds[index,3]))
        if x0>x1 or y0>y1:continue
        det=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
        if abs(det)<1e-10:continue
        yy,xx=np.mgrid[y0:y1+1,x0:x1+1]
        wa=((b[1]-c[1])*(xx-c[0])+(c[0]-b[0])*(yy-c[1]))/det
        wb=((c[1]-a[1])*(xx-c[0])+(a[0]-c[0])*(yy-c[1]))/det
        wc=1-wa-wb;inside=(wa>=-1e-6)&(wb>=-1e-6)&(wc>=-1e-6)
        weights=np.stack((wa,wb,wc),axis=-1)/denominator[indices]
        weights/=weights.sum(axis=-1,keepdims=True)
        z=weights@world[indices,2]
        target=depth[y0-start:y1+1-start,x0:x1+1];visible=inside&(z>target)
        if not visible.any():continue
        target[visible]=z[visible]
        normal_buffer[y0-start:y1+1-start,x0:x1+1][visible]=weights[visible]@normals[indices]
        position_buffer[y0-start:y1+1-start,x0:x1+1][visible]=weights[visible]@vertices[indices]
    return np.isfinite(depth),position_buffer,normal_buffer


def render_mesh(arr,p,seconds,preset):
    if not p.get('model_data') or not p['mix']:return arr
    from synth_solids import solid_frame,_plastic_surface,_grade
    from synth_prismatic import _cloud,_colors
    vertices,normals,faces,_=decode_mesh(p['model_data'])
    h,w=arr.shape[:2];(cx,cy),unit,rotation=solid_frame(p,(w,h),seconds,preset)
    world=vertices@rotation.T
    denominator=1-p['perspective']*world[:,2]/4
    projected=world[:,:2]/denominator[:,None]
    screen=projected*np.array((unit,-unit))+np.array((cx,cy))
    left=max(0,int(np.floor(screen[:,0].min()))-1);right=min(w,int(np.ceil(screen[:,0].max()))+2)
    top=max(0,int(np.floor(screen[:,1].min()))-1);bottom=min(h,int(np.ceil(screen[:,1].max()))+2)
    if left>=right or top>=bottom:return arr
    # Two samples per axis, bounded row tiles: 4K exports do not allocate
    # full-canvas supersampled position/normal/depth buffers.
    width=2*(right-left);height=2*(bottom-top)
    points=(screen-np.array((left-.25,top-.25)))*2
    triangles=points[faces]
    bounds=np.concatenate((np.ceil(triangles.min(axis=1)),np.floor(triangles.max(axis=1))),axis=1)
    result=arr.copy()
    for start in range(0,height,64):
        stop=min(height,start+64)
        hit,positions,normal_buffer=_raster_tile(points,world,denominator,vertices,normals,faces,bounds,width,start,stop)
        if not hit.any():continue
        local=positions[hit];normal=normal_buffer[hit]
        normal/=np.maximum(np.linalg.norm(normal,axis=1,keepdims=True),1e-8)
        yy,xx=np.nonzero(hit);yy+=start
        sx=(left+(xx+.5)*.5-.5-cx)/unit
        sy=-(top+(yy+.5)*.5-.5-cy)/unit
        direction=np.stack((sx*p['perspective']/4,sy*p['perspective']/4,-np.ones_like(sx)),axis=-1)@rotation
        # Both sides of open meshes remain visible with authored smooth normals.
        normal*=np.where(np.sum(normal*direction,axis=1)>0,-1.,1.)[:,None]
        if p['material']==1:
            color=_plastic_surface(local,normal,np.zeros(len(local),dtype=int),rotation,direction,dict(p,shape=2))
        else:
            t=seconds*preset['speed']
            cloud=_cloud(local[:,0]*2.8,local[:,1]*2.8,t*.22,int(preset['seed'])+101)*p['wash']*.1
            color=_colors(p['color_phase']+t*p['color_speed']+local[:,0]*.065+local[:,1]*.04+cloud,p['palette'])
            light=np.array((-.45,.65,1.));light/=np.linalg.norm(light)
            color*= (1-p['shading']*(.5-.5*np.maximum(0,(normal@rotation.T)@light)))[:,None]
            color=_grade(color,p)
        y0=top+start//2;y1=top+stop//2
        tile=np.repeat(np.repeat(arr[y0:y1,left:right],2,axis=0),2,axis=1)
        tile[hit]=tile[hit]*(1-p['mix'])+color*p['mix']
        result[y0:y1,left:right]=tile.reshape(y1-y0,2,right-left,2,3).mean(axis=(1,3))
    return result
