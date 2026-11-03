from pathlib import Path
import struct
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
root=Path(__file__).resolve().parent
def load(name):
 b=(root/name).read_bytes();n=struct.unpack_from('<I',b,80)[0]
 assert len(b)==84+50*n
 dt=np.dtype([('n','<f4',(3,)),('v','<f4',(3,3)),('a','<u2')])
 return np.frombuffer(b,dt,n,84)['v'].astype(float)
for name in ['body_dovetail_v1.stl','lid_dovetail_v1.stl','fit_rail_v1.stl','fit_lid_v1.stl']:
 v=load(name);p,ix=np.unique(v.reshape(-1,3),axis=0,return_inverse=True);f=ix.reshape(-1,3)
 e=np.sort(np.concatenate([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]]),axis=1)
 _,counts=np.unique(e,axis=0,return_counts=True)
 assert np.all(counts==2),(name,'non-manifold edges',np.sum(counts!=2))
 vol=np.einsum('ij,ij->i',v[:,0],np.cross(v[:,1],v[:,2])).sum()/6
 print(name,'triangles',len(v),'extent',np.round(np.ptp(p,axis=0),3),'closed_edges=PASS','volume',round(vol,1))
body=load('body_dovetail_v1.stl');lid=load('lid_dovetail_v1.stl')
# Undo print orientation, then lift lid for an exploded view.
lid[:,:,1]=150-lid[:,:,1];lid[:,:,2]=199.35-lid[:,:,2]+28
fig=plt.figure(figsize=(12,8));ax=fig.add_subplot(projection='3d')
for v,c in [(body,'#90b8cb'),(lid,'#e3a54c')]:
 ax.add_collection3d(Poly3DCollection(v,facecolor=c,edgecolor='#46505b',linewidth=.08))
ax.set(xlim=(-110,210),ylim=(0,150),zlim=(0,235),xlabel='X (mm)',ylabel='Y (mm)',zlabel='Z (mm)')
ax.set_box_aspect((320,150,235));ax.view_init(32,-54)
ax.set_title('Dovetail lid v1 - exploded preview (lid lifted 28 mm)')
fig.tight_layout();fig.savefig(root/'dovetail_assembly_preview.png',dpi=170)

# Cleaner views without mesh triangulation lines. The same exported STL is
# used, so these are model renders, not imagined product illustrations.
lid[:,:,2]-=28
fig=plt.figure(figsize=(15,8),facecolor='#f3f5f7')
for j,(lift,title) in enumerate([(0,'Assembled'),(32,'Lid lifted to show the sliding rails')]):
 ax=fig.add_subplot(1,2,j+1,projection='3d',facecolor='#f3f5f7')
 for mesh,c in [(body,'#759cac'),(lid+np.array([0,0,lift]),'#dda45d')]:
  collection=Poly3DCollection(mesh,facecolors=c,linewidth=0,
                            shade=True,lightsource=matplotlib.colors.LightSource(azdeg=315,altdeg=50))
  ax.add_collection3d(collection)
 ax.set(xlim=(-113,213),ylim=(-5,155),zlim=(0,238))
 ax.set_box_aspect((326,160,238));ax.view_init(32,-54);ax.set_axis_off()
 ax.set_title(title,fontsize=15,pad=0,color='#263746')
fig.suptitle('Existing enclosure + dovetail sliding lid v1',fontsize=19,color='#263746')
fig.text(.5,.04,'Blue: modified body   |   Amber: lid   |   Actual STL geometry; print fit pending',
         ha='center',fontsize=11,color='#52606d')
fig.subplots_adjust(left=0,right=1,bottom=.05,top=.91,wspace=0)
fig.savefig(root/'enclosure_lid_views.png',dpi=180,facecolor=fig.get_facecolor())
