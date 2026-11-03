from pathlib import Path
import sys,subprocess,socket,time,json,numpy as np,hashlib
root=Path('/root/rml24_tx_precision_24rf_20261101');release=Path('/opt/rml24-integrated/current').resolve();base=Path('/root/rml24_gainfreeze_integration_20261101/candidate/candidate/rml24_final');sys.path.insert(0,str(base/'board_runtime'));sys.path.insert(0,str(base/'recovery'))
from rml24_dualmode_receiver_centered_v2 import infer
import candidate_two_dc as recovery
selected=[7, 8, 10, 11, 12, 14, 15, 17, 18, 21, 22, 24, 25, 28, 29, 31, 32, 35, 36, 38, 39, 41, 42, 43, 45, 46, 48, 49, 50, 52, 53, 55, 56, 59, 60, 62, 63, 66, 67, 69, 70, 72, 73, 76, 77, 79, 80, 83, 84, 86, 87]
worker=None;conn=None;rows=[];log=(root/'classification_npu.log').open('wb')
subprocess.run(['systemctl','stop','rml24-integrated'],check=True)
try:
 sock=root/'classify.sock';assert not Path('/var/lib/rml24-fpga-shared-guard/reset_required.json').exists()
 cmd=[sys.executable,str(release/'scripts/hardware_restart_guard.py'),'--state-dir','/var/lib/rml24-fpga-shared-guard','/root/rml24_fpga_shared_owner_20261031/build/npu_stream_shared','/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16/rml24_adamrv11_bf16.json','/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16/rml24_adamrv11_bf16.raw',str(sock)];worker=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT)
 for _ in range(120):
  if sock.exists():break
  assert worker.poll() is None;time.sleep(.25)
 conn=socket.socket(socket.AF_UNIX);conn.settimeout(30);conn.connect(str(sock))
 for i in selected:
  x,meta=recovery.recover(np.load(root/('raw_%03d.npy'%i)));z=x.mean(axis=0);w=np.tile(z,(8,1));t=np.stack([w.real,w.imag],axis=1).astype('<f4');rows.append(dict(index=i,metadata=meta,input_sha=hashlib.sha256(t.tobytes()).hexdigest(),prediction=infer(conn,t)))
  (root/'CLASSIFICATION_PROGRESS.json').write_text(json.dumps(rows))
 conn.close();conn=None;assert worker.wait(timeout=30)==0
finally:
 if conn is not None:conn.close()
 if worker is not None and worker.poll() is None:worker.wait(timeout=30)
 log.close();clean=not Path('/var/lib/rml24-fpga-shared-guard/reset_required.json').exists();(root/'CLASSIFICATION_RESULT.json').write_text(json.dumps(dict(rows=rows,truth_not_supplied=True,guard_clean=clean)))
 if clean:subprocess.run(['systemctl','start','rml24-integrated'],check=True)
 else:raise RuntimeError('guard remains; baseline restart withheld')
print('CLASSIFICATION_DONE_AND_SERVICE_RESTORED',len(rows),flush=True)
