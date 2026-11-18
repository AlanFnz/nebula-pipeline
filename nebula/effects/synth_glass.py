"""Dark studio glass: Fresnel reflections and a refracted screen-space background.

An art-directed approximation, not path tracing. Samples only the incoming
image, so preview seeking is deterministic and no feedback is introduced.
"""
import numpy as np


def _sample(image, x, y):
    h,w=image.shape[:2]
    x=np.clip(x,0,w-1);y=np.clip(y,0,h-1)
    x0=x.astype(int);y0=y.astype(int);x1=np.minimum(x0+1,w-1);y1=np.minimum(y0+1,h-1)
    u=(x-x0)[:,None];v=(y-y0)[:,None]
    return ((image[y0,x0]*(1-u)+image[y0,x1]*u)*(1-v)+
            (image[y1,x0]*(1-u)+image[y1,x1]*u)*v)


def glass_surface(normal, rotation, direction, p, background, x, y, unit, local):
    normal=normal@rotation.T
    normal=normal/np.maximum(np.linalg.norm(normal,axis=1,keepdims=True),1e-8)
    view=-direction@rotation.T
    view/=np.maximum(np.linalg.norm(view,axis=1,keepdims=True),1e-8)
    cosine=np.clip(np.sum(normal*view,axis=1),0,1)
    reflected=2*cosine[:,None]*normal-view
    reflected-= (local@rotation.T)*.65
    reflected/=np.maximum(np.linalg.norm(reflected,axis=1,keepdims=True),1e-8)
    fresnel=.045+.955*(1-cosine)**5
    rough=p.get('roughness',.32)
    # Two softbox strips remain in world space as the figure rotates.
    reflection=np.full_like(normal,.018)
    for center,strength,tint in (((-.85,.55,.65),3.8,(.9,.95,1.)),((.9,-.25,.5),2.5,(1.,.94,.87))):
        light=np.array(center);light/=np.linalg.norm(light)
        tangent=np.cross((0.,1.,0.),light);tangent/=np.linalg.norm(tangent)
        up=np.cross(light,tangent)
        facing=np.maximum(0.,reflected@light)
        side=reflected@tangent;vertical=reflected@up
        box=np.exp(-.5*(side/(.10+rough*.38))**2-.5*(vertical/(.65+rough*.3))**4)*facing**3
        reflection+=box[:,None]*strength*np.array(tint)
    # Small position-dependent gradients give broad planar facets readable depth.
    rim=fresnel[:,None]*np.array((.18,.2,.23))
    shift=unit*p.get('glass_refraction',.18)
    transmission=_sample(background,x-normal[:,0]*shift,y+normal[:,1]*shift)
    density=p.get('glass_transmission',.10)*(.3+.7*cosine**2)
    base=np.array((.012,.015,.02))*(.65+.35*cosine[:,None])
    color=base+transmission*density[:,None]*(1-fresnel[:,None])
    color+=(reflection*(.12+.88*fresnel[:,None])+rim)*p.get('specular',.5)
    return np.asarray(np.clip(color*p['light'],0,1),np.float32)
