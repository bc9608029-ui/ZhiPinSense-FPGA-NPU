from pathlib import Path
import sys,json,time,numpy as np
from scipy.signal import resample_poly
from fractions import Fraction
sys.path.insert(0,'/root/amr_rescue_20261025');import pluto_link_probe as link
sys.path.insert(0,str(Path(__file__).parent));from adaptive_repeat_recovery import recover_auto
root=Path('/root/rml24_samplerate_experiment_20261101/attempt3');root.mkdir(parents=True,exist_ok=True);u=link.scan_usb();assert len(u)==1;r=link.Radio(u[0]);rows=[]
try:
 r.config_rx()
 for mode,gain,bw in [('fast_attack',fs,5000000) for fs in (5120000,)]:
  r.set(r.rx,'gain_control_mode',mode)
  hardware_fs=max(gain,2560000);r.set(r.rx,'sampling_frequency',hardware_fs);actual_fs=int(r.get(r.rx,'sampling_frequency'));assert abs(actual_fs-hardware_fs)<=20,(actual_fs,hardware_fs)
  r.set(r.rx,'rf_bandwidth',bw);time.sleep(.3)
  for k in range(5):
   y=np.asarray(r.receive(65536));name='raw_%03d.npy'%len(rows);np.save(root/('unresampled_'+name),y);y=resample_poly(y,1,2) if gain==1280000 else y;effective_fs=1280000 if gain==1280000 else actual_fs;ratio=Fraction(2560000,effective_fs).limit_denominator(1024);y=resample_poly(y,ratio.numerator,ratio.denominator).astype(np.complex64);np.save(root/name,y);d=dict(file=name,mode=mode,requested_gain=None,requested_samplerate=gain,actual_samplerate=actual_fs,effective_samplerate=effective_fs,digital_decimation_only=(gain==1280000),model_samplerate=2560000,actual_gain=r.get(r.rx,'hardwaregain'),bandwidth=r.get(r.rx,'rf_bandwidth'),rms=float(np.sqrt(np.mean(abs(y)**2))),peak=float(max(abs(y.real).max(),abs(y.imag).max())))
   try:x,meta=recover_auto(y);d.update(recovered=True,metadata=meta)
   except Exception as e:d.update(recovered=False,error=str(e))
   rows.append(d);(root/'CAPTURE_PROGRESS.json').write_text(json.dumps(rows,indent=2))
finally:
 errors=r.close();(root/'CAPTURE_RESULT.json').write_text(json.dumps(dict(rows=rows,restore_errors=errors,inference_performed=False),indent=2));print('CAPTURE_DONE',len(rows),errors,flush=True)
