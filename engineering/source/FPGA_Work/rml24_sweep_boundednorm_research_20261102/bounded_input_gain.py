import numpy as np
MIN_POWER=.8
MAX_POWER=1.25

def normalize_small_gain(tensor):
 x=np.asarray(tensor)
 if x.shape!=(8,2,1024) or not np.isfinite(x).all():raise ValueError('finite 8x2x1024 model tensor required')
 z=x[:,0,:]+1j*x[:,1,:];power=float(np.mean(np.abs(z)**2));active=MIN_POWER<=power<=MAX_POWER
 if active:
  rms=np.sqrt(np.mean(np.abs(z)**2));w=z/rms;out=np.stack([w.real,w.imag],axis=1).astype('<f4')
 else:out=tensor
 return out,dict(applied=active,input_power=power,scale=float(1/np.sqrt(power)) if active else 1.,power_window=[MIN_POWER,MAX_POWER])
