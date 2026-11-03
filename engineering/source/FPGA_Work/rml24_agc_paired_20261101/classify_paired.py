from pathlib import Path
import sys,subprocess,socket,time,json,numpy as np,hashlib
base=Path('/root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031');sys.path.insert(0,str(base));from adaptive_repeat_recovery import recover_auto
release=Path('/opt/rml24-integrated/current').resolve();sys.path.insert(0,str(release/'candidate/rml24_final/board_runtime'));from rml24_dualmode_receiver_centered_v2 import infer
root=Path('/root/rml24_agc_paired_20261101');result=root/'fast_attack/CAPTURE_RESULT.json'
for _ in range(900):
 if result.exists():break
 time.sleep(1)
assert result.exists();time.sleep(5)
subprocess.run(['systemctl','stop','rml24-integrated'],check=True);worker=None;conn=None;rows=[];log=(root/'classification_npu.log').open('wb')
try:
 sock=root/'classify.sock';assert not Path('/var/lib/rml24-fpga-shared-guard/reset_required.json').exists()
 cmd=[sys.executable,str(release/'scripts/hardware_restart_guard.py'),'--state-dir','/var/lib/rml24-fpga-shared-guard','/root/rml24_fpga_shared_owner_20261031/build/npu_stream_shared','/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16/rml24_adamrv11_bf16.json','/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16/rml24_adamrv11_bf16.raw',str(sock)];worker=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT)
 for _ in range(120):
  if sock.exists():break
  assert worker.poll() is None;time.sleep(.25)
 conn=socket.socket(socket.AF_UNIX);conn.settimeout(30);conn.connect(str(sock))
 for folder in (root/'manual',root/'slow_attack',root/'fast_attack'):
  captures=json.loads((folder/'CAPTURE_RESULT.json').read_text())['rows']
  for c in captures:
   d=dict(capture_mono_ns=c['capture_mono_ns'],folder=str(folder),file=c['file'],mode=c['mode'],actual_gain=c['actual_gain'],bandwidth=c['bandwidth'])
   try:
    x,meta=recover_auto(np.load(folder/c['file']));z=x.mean(axis=0);w=np.tile(z,(8,1));t=np.stack([w.real,w.imag],axis=1).astype('<f4');d.update(metadata=meta,input_sha=hashlib.sha256(t.tobytes()).hexdigest(),prediction=infer(conn,t),recovered=True)
   except RuntimeError as e:d.update(recovered=False,error=str(e))
   rows.append(d);(root/'CLASSIFICATION_PROGRESS.json').write_text(json.dumps(rows,indent=2))
 conn.close();conn=None;assert worker.wait(timeout=30)==0
finally:
 if conn is not None:conn.close()
 if worker is not None and worker.poll() is None:worker.wait(timeout=30)
 log.close();(root/'CLASSIFICATION_RESULT.json').write_text(json.dumps(dict(rows=rows,truth_not_supplied=True),indent=2));subprocess.run(['systemctl','start','rml24-integrated'],check=True)
print('CLASSIFICATION_DONE_AND_SERVICE_RESTORED',len(rows),flush=True)
