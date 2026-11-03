from pathlib import Path
import sys,time,json,subprocess,shutil,numpy as np
root=Path('/root/rml24_single_repeat_precision_rf_20261101');root.mkdir(exist_ok=False)
base=Path('/root/rml24_gainfreeze_integration_20261101/candidate/candidate/rml24_final')
sys.path.insert(0,str(base/'runtime'));sys.path.insert(0,str(base/'recovery'));sys.path.insert(0,str(base/'board_runtime'));sys.path.insert(0,str(Path(__file__).parent))
from scan_runtime import detect_public_training
import single_repeat_recovery_ref as recovery
from locked_detector import detect_locked
from gain_freeze_radio import install
install('/root/amr_rescue_20261025')
import pluto_link_probe as link
radio=None;rows=[];restore=[]
try:
 assert shutil.disk_usage('/').free>int(1.2*1024**3)
 subprocess.run(['systemctl','stop','rml24-integrated'],check=True)
 assert not Path('/var/lib/rml24-fpga-shared-guard/reset_required.json').exists()
 uris=link.scan_usb();assert len(uris)==1
 radio=link.Radio(uris[0]);radio.config_rx();radio.set(radio.rlo,'frequency',2403600000)
 end=time.monotonic()+210
 while time.monotonic()<end and len(rows)<260:
  raw=np.asarray(radio.receive(65536));stamp=time.monotonic_ns();name='raw_%03d.npy'%len(rows);np.save(root/name,raw)
  d=detect_public_training(raw,recovery.train);new=detect_locked(raw,recovery.train)
  r=dict(index=len(rows),capture_monotonic_ns=stamp,file=name,old=dict(score=d.score,coarse_cfo_hz=d.coarse_cfo_hz,start=d.start),new=new,gain=radio.gain_freeze_last)
  r['old_accepted']=d.score>=.10 and abs(d.coarse_cfo_hz)<=1000;r['new_accepted']=new['score']>=.10 and abs(new['coarse_cfo_hz'])<=1000
  try:
   x,meta=recovery.recover_auto(raw);r.update(recovered=True,recovery=meta)
  except RuntimeError as e:r.update(recovered=False,error=str(e))
  rows.append(r);(root/'PROGRESS.json').write_text(json.dumps(rows))
finally:
 if radio is not None:restore=radio.close() or []
 subprocess.run(['systemctl','start','rml24-integrated'],check=True)
 (root/'RESULT.json').write_text(json.dumps(dict(rows=rows,restore_errors=restore,classification_tested=False)))
 print('LOCKED_DIAG_COMPLETE',len(rows),restore,flush=True)
