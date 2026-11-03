from pathlib import Path
import sys,json,time,numpy as np
sys.path.insert(0,'/root/amr_rescue_20261025');import pluto_link_probe as link
sys.path.insert(0,str(Path(__file__).parent));from adaptive_repeat_recovery import recover_auto
root=Path('/root/rml24_repeat_agc_experiment_20261101/variable_repeats');root.mkdir(parents=True,exist_ok=True);u=link.scan_usb();assert len(u)==1;r=link.Radio(u[0]);rows=[]
try:
 r.config_rx()
 for mode,gain,bw in [('fast_attack',None,5000000)]:
  r.set(r.rx,'gain_control_mode',mode)
  if gain is not None:r.set(r.rx,'hardwaregain',gain)
  r.set(r.rx,'rf_bandwidth',bw);time.sleep(.3)
  deadline=time.monotonic()+115
  for k in range(300):
   if time.monotonic()>deadline:break
   y=np.asarray(r.receive(65536));name='raw_%03d.npy'%len(rows);np.save(root/name,y);d=dict(capture_mono_ns=time.monotonic_ns(),file=name,mode=mode,requested_gain=gain,actual_gain=r.get(r.rx,'hardwaregain'),bandwidth=r.get(r.rx,'rf_bandwidth'),rms=float(np.sqrt(np.mean(abs(y)**2))),peak=float(max(abs(y.real).max(),abs(y.imag).max())))
   try:x,meta=recover_auto(y);d.update(recovered=True,metadata=meta)
   except Exception as e:d.update(recovered=False,error=str(e))
   rows.append(d);(root/'CAPTURE_PROGRESS.json').write_text(json.dumps(rows,indent=2))
finally:
 errors=r.close();(root/'CAPTURE_RESULT.json').write_text(json.dumps(dict(rows=rows,restore_errors=errors,inference_performed=False),indent=2));print('CAPTURE_DONE',len(rows),errors,flush=True)
