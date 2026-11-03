import numpy as np
from scipy.signal import correlate,find_peaks

def detect_locked(raw,train,fs=2560000):
 raw=np.asarray(raw,dtype=np.complex128);train=np.asarray(train,dtype=np.complex128)
 if raw.ndim!=1 or train.shape!=(2048,) or not np.isfinite(raw).all():raise ValueError('invalid capture')
 # Only for an already verified centered LO. Broad acquisition remains separate.
 centered=raw-raw.mean();c=correlate(centered,train,mode='valid',method='fft');peaks,_=find_peaks(abs(c),distance=512)
 if not len(peaks):raise RuntimeError('no locked pilot candidate')
 best=None;n=np.arange(2048);te=float(np.vdot(train,train).real)
 for start in sorted(peaks,key=lambda i:abs(c[i]),reverse=True)[:12]:
  segment=raw[start:start+2048];u=segment[:1024];v=segment[1024:];lag=np.vdot(u-u.mean(),v-v.mean());f=float(np.angle(lag)*fs/(2*np.pi*1024));coherent=abs(np.sum(segment*np.conj(train)*np.exp(-2j*np.pi*f*n/fs)));score=float(coherent/np.sqrt(max(float(np.vdot(segment,segment).real)*te,1e-24)))
  result=dict(start=int(start),coarse_cfo_hz=f,score=min(score,1.0))
  if best is None or score>best['score']:best=result
 return best
