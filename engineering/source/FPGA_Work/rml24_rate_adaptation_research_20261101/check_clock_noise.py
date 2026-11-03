import os
os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['OMP_NUM_THREADS']='1'
import sys,json,time
from pathlib import Path
import numpy as np
from scipy.signal import resample_poly
p=Path('E:/FPGA_Work/rml24_rate_adaptation_research_20261101')
sys.path.insert(0,str(p));sys.path.insert(0,'E:/FPGA_Work/rml24_repeat_agc_experiment_20261101')
from rate_recovery import recover_rate_and_repeats
from adaptive_repeat_recovery import train,tail
from experimental_frame import build_frame
rng=np.random.default_rng(193811)
x=np.exp(1j*np.pi/2*rng.integers(0,4,1024)).astype(np.complex64)
b=np.stack([x.real,x.imag]).astype('<f4').tobytes()
rows=[]
for ppm in (-100,-50,0,50,100):
 f=build_frame(b,train,tail,8)
 a=np.tile(resample_poly(f,2,1),5)
 t=np.arange(131072)*(1+ppm/1e6)
 z=np.interp(t,np.arange(len(a)),a.real)+1j*np.interp(t,np.arange(len(a)),a.imag)
 z=.2*z*np.exp(2j*np.pi*100*np.arange(len(z))/5120000)+.1+.07j+.3*(rng.normal(size=len(z))+1j*rng.normal(size=len(z)))
 try:
  recovered,m=recover_rate_and_repeats(z)
  err=float(np.linalg.norm(recovered.reshape(-1)[:1024]-x)/np.linalg.norm(x))
  rows.append(dict(ppm=ppm,recovered=True,relative_error=err,meta=m))
 except RuntimeError as e:rows.append(dict(ppm=ppm,recovered=False,error=str(e)))
 (p/'CLOCK_NOISE_PROGRESS.json').write_text(json.dumps(rows,indent=2))
 print('CLOCK',ppm,rows[-1].get('relative_error','REJECT'),flush=True)
noise=[]
for i in range(12):
 z=rng.normal(size=65536)+1j*rng.normal(size=65536)
 try:
  _,m=recover_rate_and_repeats(z);noise.append(dict(index=i,accepted=True,meta=m))
 except RuntimeError:noise.append(dict(index=i,accepted=False))
 print('NOISE',i,noise[-1]['accepted'],flush=True)
result=dict(scope='PC synthetic only; no RF or NPU classification; frozen formal unchanged',clock=rows,noise=noise,false_accepts=sum(r['accepted'] for r in noise))
(p/'CLOCK_NOISE_RESULT.json').write_text(json.dumps(result,indent=2))
