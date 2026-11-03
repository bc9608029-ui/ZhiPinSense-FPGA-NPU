from pathlib import Path
import sys,json,time,numpy as np,shutil
sys.path.insert(0,'/root/amr_rescue_20261025');import pluto_link_probe as link
sys.path.insert(0,str(Path(__file__).parent));from weak_adaptive_recovery import recover_auto
root=Path('/root/rml24_weak_adaptive_rf_20261101')/sys.argv[1];root.mkdir(parents=True,exist_ok=True);assert shutil.disk_usage(root).free>800*1024*1024;u=link.scan_usb();assert len(u)==1;r=link.Radio(u[0]);rows=[]
try:
 r.config_rx()
 for mode,gain,bw in [('manual',35,int(sys.argv[1].split('bw')[1])*1000000)]:
  r.set(r.rx,'gain_control_mode',mode)
  if gain is not None:r.set(r.rx,'hardwaregain',gain)
  r.set(r.rx,'rf_bandwidth',bw);time.sleep(.3)
  deadline=time.monotonic()+435
  for k in range(2000):
   if time.monotonic()>deadline:break
   if sys.argv[1].startswith('gainfreeze'):
    r.set(r.rx,'gain_control_mode','slow_attack')
    for settle in range(3):r.receive(16384)
    selected_gain=float(r.get(r.rx,'hardwaregain').split()[0]);r.set(r.rx,'gain_control_mode','manual');r.set(r.rx,'hardwaregain',selected_gain)
   capture_time=time.monotonic_ns();y=np.asarray(r.receive(65536));name='raw_%03d.npy'%len(rows);np.save(root/name,y);d=dict(capture_mono_ns=capture_time,file=name,mode=sys.argv[1],requested_gain=(selected_gain if sys.argv[1].startswith('gainfreeze') else gain),actual_gain=r.get(r.rx,'hardwaregain'),bandwidth=r.get(r.rx,'rf_bandwidth'),rms=float(np.sqrt(np.mean(abs(y)**2))),peak=float(max(abs(y.real).max(),abs(y.imag).max())))
   try:x,meta=recover_auto(y);d.update(recovered=True,metadata=meta)
   except Exception as e:d.update(recovered=False,error=str(e))
   rows.append(d);(root/'CAPTURE_PROGRESS.json').write_text(json.dumps(rows,indent=2))
finally:
 errors=r.close();(root/'CAPTURE_RESULT.json').write_text(json.dumps(dict(rows=rows,restore_errors=errors,inference_performed=False),indent=2));print('CAPTURE_DONE',len(rows),errors,flush=True)
