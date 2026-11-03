import numpy as np
from scipy.signal import correlate,find_peaks
def repeat_consistency(y,train,repeats=8):
 c=abs(correlate(y,train,mode='valid',method='fft'));peaks,_=find_peaks(c,distance=7000);end=2048+repeats*1024;peaks=sorted([int(k) for k in peaks if k+end<=len(y)],key=lambda k:c[k],reverse=True)[:4]
 if len(peaks)<2:return dict(eligible=False,reason='too few frames')
 z=[]
 for k in peaks:
  u=y[k:k+1024];v=y[k+1024:k+2048];f=np.angle(np.vdot(u-u.mean(),v-v.mean()))*2560000/(2*np.pi*1024);q=y[k+2048:k+end]*np.exp(-2j*np.pi*f*np.arange(2048,end)/2560000);q=q.reshape(repeats,1024).mean(axis=0);q=q-q.mean();z.append(q)
 similarities=[]
 for i in range(len(z)):
  for j in range(i):similarities.append(float(abs(np.vdot(z[i],z[j]))/max(np.linalg.norm(z[i])*np.linalg.norm(z[j]),1e-12)))
 score=float(np.median(similarities));return dict(eligible=score>=.8,median_similarity=score,frames=len(peaks),threshold=.8,scope='experimental gate; synthetic validation only')
