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
for ppm in (-73,-23,27,77):
 f=build_frame(b,train,tail,8)
 a=np.tile(resample_poly(f,2,1),5)
 t=np.arange(131072)*(1+ppm/1e6)
 z=np.interp(t,np.arange(len(a)),a.real)+1j*np.interp(t,np.arange(len(a)),a.imag)
 z=.2*z*np.exp(2j*np.pi*100*np.arange(len(z))/5120000)+.1+.07j+.3*(rng.normal(size=len(z))+1j*rng.normal(size=len(z)))
 try:
  candidates=[]
  for estimate in range(-100,101,5):
   q=np.arange(len(z))/(1+estimate/1e6)
   corrected=np.interp(q,np.arange(len(z)),z.real)+1j*np.interp(q,np.arange(len(z)),z.imag)
   try:
    candidate,cm=recover_rate_and_repeats(corrected)
    quality=max(cm['head_reference_relative_error'],cm['tail_reference_relative_error'])
    candidates.append((quality,estimate,candidate,cm))
   except RuntimeError:pass
  if not candidates:raise RuntimeError('no clock grid candidate')
  _,estimate,recovered,m=min(candidates,key=lambda c:c[0]);m['estimated_clock_ppm']=estimate
  err=float(np.linalg.norm(recovered.reshape(-1)[:1024]-x)/np.linalg.norm(x))
  rows.append(dict(ppm=ppm,recovered=True,relative_error=err,meta=m))
 except RuntimeError as e:rows.append(dict(ppm=ppm,recovered=False,error=str(e)))
 (p/'CLOCK_FINE_PROGRESS.json').write_text(json.dumps(rows,indent=2))
 print('CLOCK',ppm,rows[-1].get('relative_error','REJECT'),flush=True)
result=dict(scope='Synthetic development clock grid; no hardware or classification validation; held-out offsets are 2 ppm from nearest 5 ppm grid; synthetic only',clock=rows)
(p/'CLOCK_FINE_RESULT.json').write_text(json.dumps(result,indent=2))
