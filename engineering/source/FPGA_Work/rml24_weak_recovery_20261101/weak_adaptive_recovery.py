import numpy as np
from scipy.signal import correlate,find_peaks
from adaptive_repeat_recovery import recover_auto as original,train
def combine(y):
 c=abs(correlate(y,train,mode='valid',method='fft'));peaks,_=find_peaks(c,distance=14000);peaks=sorted([int(k) for k in peaks if k+12288<=len(y)],key=lambda k:c[k],reverse=True)[:4]
 if len(peaks)<2:raise RuntimeError('fewer than2 candidate repeated frames')
 estimates=[]
 for k in peaks:
  u=y[k:k+1024];v=y[k+1024:k+2048];estimates.append(np.angle(np.vdot(u-u.mean(),v-v.mean()))*2560000/(2*np.pi*1024))
 freq=float(np.median(estimates));n=np.arange(12288);segments=[]
 for k in peaks:
  z=y[k:k+12288]*np.exp(-2j*np.pi*freq*n/2560000);a=np.vdot(train,z[:2048]);segments.append(z*np.exp(-1j*np.angle(a)))
 z=np.mean(segments,axis=0);scale=128/max(float(np.sqrt(np.mean(abs(z-z.mean())**2))),1e-12);return np.r_[np.zeros(2048),z*scale,np.zeros(2048)].astype(np.complex64),len(peaks)

def recover_auto(y):
 try:
  x,meta=original(y);return x,dict(meta,temporal_combine=0.0)
 except RuntimeError:
  z,n=combine(y);x,meta=original(z);return x,dict(meta,temporal_combine=float(n))
