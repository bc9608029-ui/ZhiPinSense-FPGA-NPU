from pathlib import Path
import sys,json,gzip,hashlib,subprocess,socket,time,numpy as np
base=Path('/root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031');root=Path('/root/rml24_clean_source_audit_20261101');root.mkdir(exist_ok=False);release=Path('/opt/rml24-integrated/current').resolve();sys.path.insert(0,str(release/'candidate/rml24_final/board_runtime'));from rml24_dualmode_receiver_centered_v2 import infer
raw=gzip.decompress((base/'clean_inputs.gz').read_bytes());v=np.frombuffer(raw,dtype='<f4').reshape(24,2,1024);assert np.isfinite(v).all();subprocess.run(['systemctl','stop','rml24-integrated'],check=True);conn=None;worker=None;rows=[];log=(root/'npu.log').open('wb')
try:
 assert not Path('/var/lib/rml24-fpga-shared-guard/reset_required.json').exists();sock=root/'npu.sock';cmd=[sys.executable,str(release/'scripts/hardware_restart_guard.py'),'--state-dir','/var/lib/rml24-fpga-shared-guard','/root/rml24_fpga_shared_owner_20261031/build/npu_stream_shared','/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16/rml24_adamrv11_bf16.json','/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16/rml24_adamrv11_bf16.raw',str(sock)];worker=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT)
 for _ in range(120):
  if sock.exists():break
  assert worker.poll() is None;time.sleep(.25)
 conn=socket.socket(socket.AF_UNIX);conn.settimeout(30);conn.connect(str(sock))
 for i,x in enumerate(v):
  rows.append(dict(index=i,source_sha=hashlib.sha256(x.tobytes()).hexdigest(),prediction=infer(conn,np.repeat(x[None,:,:],8,axis=0))))
 conn.close();conn=None;assert worker.wait(timeout=30)==0
finally:
 if conn is not None:conn.close()
 if worker is not None and worker.poll() is None:worker.wait(timeout=30)
 log.close();(root/'RESULT.json').write_text(json.dumps(rows,indent=2));assert not Path('/var/lib/rml24-fpga-shared-guard/reset_required.json').exists();subprocess.run(['systemctl','start','rml24-integrated'],check=True)
print('CLEAN_SOURCE_AUDIT_COMPLETE',len(rows),flush=True)
