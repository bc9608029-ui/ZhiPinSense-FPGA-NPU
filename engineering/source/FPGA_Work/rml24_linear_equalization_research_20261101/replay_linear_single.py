from pathlib import Path
import sys,subprocess,socket,time,json,numpy as np,hashlib
root=Path('/root/rml24_linear_single_replay_20261101');root.mkdir(exist_ok=False);rawroot=Path('/root/rml24_single_repeat_precision_rf_20261101');release=Path('/opt/rml24-integrated/current').resolve();base=Path('/root/rml24_gainfreeze_integration_20261101/candidate/candidate/rml24_final');sys.path.insert(0,str(base/'board_runtime'));sys.path.insert(0,str(base/'recovery'))
from rml24_dualmode_receiver_centered_v2 import infer
from linear_single_recovery_ref import recover_linear
selected=[5, 7, 8, 9, 10, 12, 14, 15, 16, 17, 19, 21, 22, 24, 26, 27, 29, 31, 33, 34, 36, 38, 39, 41, 43, 45, 46, 48, 50, 51, 53, 55, 57, 58, 60]
worker=None;conn=None;rows=[];raw_statistics=[];pure_cases=[];log=(root/'classification_npu.log').open('wb')
subprocess.run(['systemctl','stop','rml24-integrated'],check=True)
try:
 sock=root/'classify.sock';assert not Path('/var/lib/rml24-fpga-shared-guard/reset_required.json').exists()
 cmd=[sys.executable,str(release/'scripts/hardware_restart_guard.py'),'--state-dir','/var/lib/rml24-fpga-shared-guard','/root/rml24_fpga_shared_owner_20261031/build/npu_stream_shared','/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16/rml24_adamrv11_bf16.json','/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16/rml24_adamrv11_bf16.raw',str(sock)];worker=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT)
 for _ in range(120):
  if sock.exists():break
  assert worker.poll() is None;time.sleep(.25)
 conn=socket.socket(socket.AF_UNIX);conn.settimeout(30);conn.connect(str(sock))
 for i in selected:
  raw=np.load(rawroot/('raw_%03d.npy'%i));components=np.r_[raw.real,raw.imag]
  raw_statistics.append(dict(index=i,min=float(components.min()),max=float(components.max()),component_peak=float(abs(components).max()),q999_abs=float(np.quantile(abs(components),.999)),at_12bit_rails=int(np.sum((components==-2048)|(components==2047))),above_12bit_range=int(np.sum((components<-2048)|(components>2047))),near_12bit_rails_fraction=float(np.mean(abs(components)>=2000))))
  try:x,meta=recover_linear(raw)
  except RuntimeError as e:
   rows.append(dict(index=i,recovered=False,error=str(e)));continue
  z=x.mean(axis=0);w=np.tile(z,(8,1));t=np.stack([w.real,w.imag],axis=1).astype('<f4');rows.append(dict(index=i,recovered=True,metadata=meta,input_sha=hashlib.sha256(t.tobytes()).hexdigest(),prediction=infer(conn,t)))
  (root/'CLASSIFICATION_PROGRESS.json').write_text(json.dumps(rows))
 import gzip
 bank=np.frombuffer(gzip.decompress((Path(__file__).parent/'PERSISTENT_INPUTS.gz').read_bytes()),dtype='<f4').reshape(-1,8,2,1024)
 for index,t in enumerate(bank):pure_cases.append(dict(index=index,input_sha=hashlib.sha256(t.tobytes()).hexdigest(),prediction=infer(conn,t)))
 conn.close();conn=None;assert worker.wait(timeout=30)==0
finally:
 if conn is not None:conn.close()
 if worker is not None and worker.poll() is None:worker.wait(timeout=30)
 log.close();clean=not Path('/var/lib/rml24-fpga-shared-guard/reset_required.json').exists();(root/'CLASSIFICATION_RESULT.json').write_text(json.dumps(dict(rows=rows,raw_statistics=raw_statistics,pure_cases=pure_cases,truth_not_supplied=True,guard_clean=clean)))
 if clean:subprocess.run(['systemctl','start','rml24-integrated'],check=True)
 else:raise RuntimeError('guard remains; baseline restart withheld')
print('CLASSIFICATION_DONE_AND_SERVICE_RESTORED',len(rows),flush=True)
