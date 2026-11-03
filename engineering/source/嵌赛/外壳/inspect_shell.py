from pathlib import Path
import struct
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

root=Path(__file__).resolve().parent
p=next(root.glob('*.stl'))
b=p.read_bytes(); n=struct.unpack_from('<I',b,80)[0]
if len(b)!=84+50*n: raise ValueError('Expected binary STL')
dt=np.dtype([('normal','<f4',(3,)),('vertices','<f4',(3,3)),('attr','<u2')])
v=np.frombuffer(b,dt,n,84)['vertices'].astype(float)
lo=v.reshape(-1,3).min(0);hi=v.reshape(-1,3).max(0)
print('triangles',n,'min',lo,'max',hi,'extent',hi-lo)
fig=plt.figure(figsize=(14,10))
for j,(elev,azim) in enumerate([(25,-55),(25,125),(90,-90),(0,-90)]):
 ax=fig.add_subplot(2,2,j+1,projection='3d')
 ax.add_collection3d(Poly3DCollection(v,facecolor='#90b8cb',edgecolor='#344c60',linewidth=.10,alpha=1))
 ax.set_xlim(lo[0],hi[0]);ax.set_ylim(lo[1],hi[1]);ax.set_zlim(lo[2],hi[2])
 ax.set_box_aspect(np.maximum(hi-lo,1));ax.view_init(elev,azim)
 ax.set_xlabel('X');ax.set_ylabel('Y');ax.set_zlabel('Z')
 ax.set_title(f'elev={elev}, azim={azim}')
fig.suptitle('Existing STL inspection (STL units; confirm mm)')
fig.tight_layout();fig.savefig(root/'shell_inspection.png',dpi=150)
