import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
from pathlib import Path
import sys,json,numpy as np
from scipy.signal import resample_poly,butter,sosfilt
p=Path(__file__).parent;sys.path.insert(0,'E:/FPGA_Work/rml24_repeat_agc_experiment_20261101');import adaptive_repeat_recovery as ref;from experimental_frame import build_frame
assets=Path('E:/FPGA_Work/rml24_tx_console_integration_20261031/console/assets');rows=[];fs=5120000;sos=butter(1,50,btype='highpass',fs=fs,output='sos')
for i in (14,15,17,18,19,20):
 data=(assets/('%02d_00.bin'%i)).read_bytes();a=np.frombuffer(data,'<f4').reshape(2,1024);expected=a[0]+1j*a[1]
 for count in (1,8):
  frame=build_frame(data,ref.train,ref.tail,count);base=resample_poly(np.tile(frame,12),2,1)
  for residual in (20,-70):
   for offset in (0,50000):
    z=base*np.exp(2j*np.pi*(residual+offset)*np.arange(len(base))/fs);z=sosfilt(sos,z);z=z*np.exp(-2j*np.pi*offset*np.arange(len(z))/fs);raw=resample_poly(z,1,2);start=2*len(frame);raw=raw[start:start+65536];r=dict(source=i,repeats=count,residual_cfo_hz=residual,rx_internal_offset_hz=offset)
    try:
     x,m=(ref.recover_1(raw) if count==1 else ref.recover_8(raw));mean=x.mean(axis=0);r.update(recovered=True,relative_error=float(np.linalg.norm(mean-expected)/np.linalg.norm(expected)))
    except RuntimeError as e:r.update(recovered=False,error=str(e))
    rows.append(r)
(p/'SYNTHETIC_OFFSET_RESULT.json').write_text(json.dumps(dict(scope='Concept only: chosen first-order50Hz highpass surrogate, not measured AD9361 tracking; no RF or NPU classification; RX5.12 oversampling and digital offset removal simulated',rows=rows),indent=2))
for offset in (0,50000):
 a=[r['relative_error'] for r in rows if r['rx_internal_offset_hz']==offset and r['recovered']];print('OFFSET',offset,'RECOVERED',len(a),'/24','MEDIAN_ERROR',float(np.median(a)),flush=True)
