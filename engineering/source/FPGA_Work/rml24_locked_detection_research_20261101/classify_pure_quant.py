from pathlib import Path
import sys,subprocess,socket,time,json,numpy as np,hashlib
root=Path('/root/rml24_locked_detection_research_20261101');release=Path('/opt/rml24-integrated/current').resolve();base=Path('/root/rml24_gainfreeze_integration_20261101/candidate/candidate/rml24_final');sys.path.insert(0,str(base/'board_runtime'));sys.path.insert(0,str(base/'recovery'))
from rml24_dualmode_receiver_centered_v2 import infer
import candidate_two_dc as recovery
selected=[6, 7, 8, 9, 12, 13, 14, 17, 18, 19, 22, 23, 24, 27, 28, 29, 32, 33, 34, 35]
worker=None;conn=None;rows=[];log=(root/'pure_quant_npu.log').open('wb')
subprocess.run(['systemctl','stop','rml24-integrated'],check=True)
try:
 sock=root/'pure_quant.sock';assert not Path('/var/lib/rml24-fpga-shared-guard/reset_required.json').exists()
 cmd=[sys.executable,str(release/'scripts/hardware_restart_guard.py'),'--state-dir','/var/lib/rml24-fpga-shared-guard','/root/rml24_fpga_shared_owner_20261031/build/npu_stream_shared','/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16/rml24_adamrv11_bf16.json','/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16/rml24_adamrv11_bf16.raw',str(sock)];worker=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT)
 for _ in range(120):
  if sock.exists():break
  assert worker.poll() is None;time.sleep(.25)
 conn=socket.socket(socket.AF_UNIX);conn.settimeout(30);conn.connect(str(sock))
 import gzip
 bank=np.frombuffer(gzip.decompress((Path(__file__).parent/'PURE_QUANT_INPUTS.gz').read_bytes()),dtype='<f4').reshape(-1,8,2,1024)
 for i,t in enumerate(bank):
  rows.append(dict(index=i,input_sha=hashlib.sha256(t.tobytes()).hexdigest(),prediction=infer(conn,t)))
 conn.close();conn=None;assert worker.wait(timeout=30)==0
finally:
 if conn is not None:conn.close()
 if worker is not None and worker.poll() is None:worker.wait(timeout=30)
 log.close();clean=not Path('/var/lib/rml24-fpga-shared-guard/reset_required.json').exists();(root/'PURE_QUANT_RESULT.json').write_text(json.dumps(dict(rows=rows,truth_not_supplied=True,guard_clean=clean)))
 if clean:subprocess.run(['systemctl','start','rml24-integrated'],check=True)
 else:raise RuntimeError('guard remains; baseline restart withheld')
print('CLASSIFICATION_DONE_AND_SERVICE_RESTORED',len(rows),flush=True)
