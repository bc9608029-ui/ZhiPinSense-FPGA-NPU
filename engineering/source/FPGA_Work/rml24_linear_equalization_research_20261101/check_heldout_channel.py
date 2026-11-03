import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import sys,inspect,json,numpy as np
from pathlib import Path
from scipy.signal import fftconvolve
p=Path(__file__).parent;sys.path.insert(0,'E:/FPGA_Work/rml24_repeat_agc_experiment_20261101')
import adaptive_repeat_recovery as ref
from experimental_frame import build_frame
source=inspect.getsource(ref.recover_1).replace('def recover_1(', 'def recover_linear(')
a=source.index('        payload=((z[2048:3072]-offset)/drift)');b=source.index('        return x.reshape',a)
source=source[:a]+"""        full_w=(n-1023.5)/3072
        full_drift=1*(1-full_w)+tail_fit[0]*full_w
        signal=(z-joint[-2]-joint[-1]*dc_basis)/full_drift
        omega=2*np.pi*np.fft.fftfreq(len(signal))
        response=np.exp(-1j*omega[:,None]*lags)@joint[:-2]
        inv=np.conj(response)/(abs(response)**2+1e-4*np.max(abs(response)**2))
        all_x=np.fft.ifft(np.fft.fft(signal)*inv)
        x=all_x[2048:3072].reshape(1,1024)
"""+source[b:]
prefix='import numpy as np\nfrom scipy.signal import correlate,find_peaks\nFS=2560000\nfrom adaptive_repeat_recovery import train,tail\n';(p/'linear_single_recovery.py').write_text(prefix+source);sys.path.insert(0,str(p));import importlib;importlib.invalidate_caches();from linear_single_recovery import recover_linear
assets=Path('E:/FPGA_Work/rml24_tx_console_integration_20261031/console/assets');rng=np.random.default_rng(87122);rows=[]
for i in (14,15,17,20,22,23):
 data=(assets/('%02d_00.bin'%i)).read_bytes();v=np.frombuffer(data,'<f4').reshape(2,1024);expected=v[0]+1j*v[1]
 for delay in (-.37,.13,.67):
  frame=build_frame(data,ref.train,ref.tail,1);values=np.frombuffer(data,'<f4');peak=max(float(abs(values).max()),1/np.sqrt(2));scale=int(.95*2047/(np.sqrt(2)*peak))*np.sqrt(2);frame=frame*(scale/68.46059377833956);frame=np.rint(frame.real)+1j*np.rint(frame.imag)
  h=np.sinc(np.arange(-12,13)-delay)*np.hamming(25);h=h/h.sum();raw=fftconvolve(np.tile(frame,9),h,mode='same')[6000:71536];raw=.2*raw*np.exp(2j*np.pi*(-300)*np.arange(len(raw))/2560000)+.1+.05j+.003*scale*(rng.normal(size=len(raw))+1j*rng.normal(size=len(raw)))
  r=dict(case=i,fractional_delay=delay)
  for name,fn in [('circular1024',ref.recover_1),('fullframe_linear_context',recover_linear)]:
   try:
    x,m=fn(raw);r[name]=float(np.linalg.norm(x.reshape(-1)-expected)/np.linalg.norm(expected))
   except RuntimeError:r[name]=None
  rows.append(r)
(p/'SYNTHETIC_HELDOUT_CHANNEL_RESULT.json').write_text(json.dumps(dict(scope='Synthetic channel fidelity only, no RF or NPU classification; public head/tail context instead of per-payload circular boundary',rows=rows),indent=2));both=[r for r in rows if r['circular1024'] is not None and r['fullframe_linear_context'] is not None];print('BOTH_RECOVERED',len(both),'/',len(rows),'MEDIAN_OLD_NEW',float(np.median([r['circular1024'] for r in both])),float(np.median([r['fullframe_linear_context'] for r in both])),'IMPROVED',sum(r['fullframe_linear_context']<r['circular1024'] for r in both),flush=True)
