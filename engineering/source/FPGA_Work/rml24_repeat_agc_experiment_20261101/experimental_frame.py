import numpy as np
SCALE=68.46059377833956
def build_frame(payload_bytes,train,tail,repeats):
 if repeats not in (1,2,4,8):raise ValueError('repeats must be 1/2/4/8')
 x=np.frombuffer(payload_bytes,dtype='<f4')
 if x.size!=2048 or not np.isfinite(x).all():raise ValueError('payload')
 iq=x.reshape(2,1024);z=iq[0]+1j*iq[1]
 frame=np.concatenate([np.zeros(2048,np.complex64),np.asarray(train,np.complex64),np.tile(z,repeats),np.asarray(tail,np.complex64),np.zeros(2048,np.complex64)]).astype(np.complex64)*SCALE
 if not np.isfinite(frame).all() or max(abs(frame.real).max(),abs(frame.imag).max())>2047:raise ValueError('TX clipping')
 return frame
