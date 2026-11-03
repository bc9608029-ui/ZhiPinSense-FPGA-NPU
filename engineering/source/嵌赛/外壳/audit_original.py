from pathlib import Path
import json,struct
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
root=Path(__file__).resolve().parent
def load(name):
 b=(root/name).read_bytes();n=struct.unpack_from('<I',b,80)[0]
 dt=np.dtype([('n','<f4',(3,)),('v','<f4',(3,3)),('a','<u2')])
 return np.frombuffer(b,dt,n,84)['v'].astype(float)
def review(name):
 v=load(name);p,ix=np.unique(v.reshape(-1,3),axis=0,return_inverse=True);f=ix.reshape(-1,3)
 directed=np.concatenate([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]]);e=np.sort(directed,axis=1)
 unique,counts=np.unique(e,axis=0,return_counts=True)
 graph=coo_matrix((np.ones(len(e)),(e[:,0],e[:,1])),shape=(len(p),len(p)))
 nc,labels=connected_components(graph,directed=False)
 area=np.linalg.norm(np.cross(v[:,1]-v[:,0],v[:,2]-v[:,0]),axis=1)/2
 components=[]
 for i in range(nc):
  q=p[labels==i];components.append({'vertices':len(q),'min':q.min(0).tolist(),'max':q.max(0).tolist()})
 return dict(file=name,triangles=len(v),min=p.min(0).tolist(),max=p.max(0).tolist(),
             boundary_edges=int(np.sum(counts==1)),nonmanifold_edges=int(np.sum(counts>2)),
             degenerate_triangles=int(np.sum(area<1e-8)),connected_components=components)
def intervals(v,axis,point):
 # Exact axis-aligned line/triangle intersection; merge triangulation duplicates.
 others=[i for i in range(3) if i!=axis];t=v[:,:,others]
 a=t[:,0];u=t[:,1]-a;w=t[:,2]-a;d=np.asarray(point)-a
 det=u[:,0]*w[:,1]-u[:,1]*w[:,0];good=abs(det)>1e-10
 den=np.where(good,det,1)
 s=(d[:,0]*w[:,1]-d[:,1]*w[:,0])/den
 r=(u[:,0]*d[:,1]-u[:,1]*d[:,0])/den
 use=good&(s>=-1e-7)&(r>=-1e-7)&(s+r<=1+1e-7)
 z=v[:,0,axis]+s*(v[:,1,axis]-v[:,0,axis])+r*(v[:,2,axis]-v[:,0,axis])
 return np.unique(np.round(z[use],4)).tolist()
results=[review(n) for n in ['shell_original.stl','body_dovetail_v1.stl','lid_dovetail_v1.stl']]
v=load('shell_original.stl')
probes=[]
for axis,point,label in [(1,(50,180),'front_back_upper'),(0,(75,180),'left_right_upper'),
                          (2,(180,125),'floor_rear_right'),(2,(-80,125),'floor_rear_left'),
                          (2,(50,75),'floor_center'),(1,(50,100),'screen_center')]:
 probes.append(dict(label=label,axis=axis,point=point,intersections_mm=intervals(v,axis,point)))
report={'meshes':results,'axis_line_probes':probes}
(root/'geometry_audit').mkdir(exist_ok=True)
(root/'geometry_audit'/'mesh_and_thickness.json').write_text(json.dumps(report,indent=2),encoding='utf8')
print(json.dumps(report,indent=2))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
fig,axs=plt.subplots(1,3,figsize=(16,6))
for ax,axis,level,title in zip(axs,[0,1,2],[50,75,100],['Center side section X=50','Front section Y=75','Plan section Z=100']):
 others=[a for a in range(3) if a!=axis];segments=[]
 for tri in v:
  points=[]
  for a,b in [(0,1),(1,2),(2,0)]:
   da=tri[a,axis]-level;db=tri[b,axis]-level
   if da*db<0:
    pt=tri[a]+(tri[b]-tri[a])*(-da)/(db-da);points.append(pt[others])
  if len(points)==2:segments.append(points)
 ax.add_collection(LineCollection(segments,colors='#17566c',linewidths=1.3))
 ax.autoscale();ax.set_aspect('equal');ax.set_title(title);ax.grid(alpha=.2)
 ax.set_xlabel('XYZ'[others[0]]+' mm');ax.set_ylabel('XYZ'[others[1]]+' mm')
fig.tight_layout();fig.savefig(root/'geometry_audit'/'body_sections.png',dpi=160)
