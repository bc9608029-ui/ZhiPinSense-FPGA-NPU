from pathlib import Path
import sys,subprocess,socket,time,json,numpy as np,hashlib
root=Path('/root/rml24_amplitude_normalization_audit_20261102');cap=root/'inputs';release=Path('/opt/rml24-integrated/current').resolve();base=Path('/root/rml24_gain_headroom_centerfix_20261101/candidate/candidate/rml24_final');sys.path.insert(0,str(base/'board_runtime'));sys.path.insert(0,str(base/'recovery'))
from rml24_dualmode_receiver_centered_v2 import infer
assert 'rml24_pl_sha256=f42dd12f03bf81c65978b7034b45808efd5035f6a358cc54710f2404530a057c' in Path('/proc/cmdline').read_text()
worker_path=Path('/root/rml24_fpga_shared_owner_20261031/build/npu_stream_shared');assert hashlib.sha256(worker_path.read_bytes()).hexdigest()=='7b185cad8aaf526344a36666a90071e59577a2fa1488a7f8f0523ce437bc0af9'
frames=tuple(range(240));worker=None;conn=None;rows=[];log=(root/'normalization_npu.log').open('wb');subprocess.run(['systemctl','stop','rml24-integrated'],check=True)
try:
 sock=root/'normalization.sock';assert not Path('/var/lib/rml24-fpga-shared-guard/reset_required.json').exists()
 cmd=[sys.executable,str(release/'scripts/hardware_restart_guard.py'),'--state-dir','/var/lib/rml24-fpga-shared-guard',str(worker_path),'/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16/rml24_adamrv11_bf16.json','/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16/rml24_adamrv11_bf16.raw',str(sock)];worker=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT)
 for _ in range(120):
  if sock.exists():break
  assert worker.poll() is None;time.sleep(.25)
 conn=socket.socket(socket.AF_UNIX);conn.settimeout(30);conn.connect(str(sock))
 for frame in frames:
  data=(cap/('%03d.bin'%frame)).read_bytes();x=np.frombuffer(data,'<f4').reshape(2,1024);z=np.tile(x[0]+1j*x[1],(8,1));rms=np.sqrt(np.mean(abs(z)**2));variants={'original':z,'unit_rms':z/max(float(rms),1e-12)}
  for name,a in variants.items():
   tensor=np.stack([a.real,a.imag],axis=1).astype('<f4');result=infer(conn,tensor);rows.append(dict(frame_id=frame,variant=name,input_sha256=hashlib.sha256(tensor.tobytes()).hexdigest(),prediction=result));(root/'NORMALIZATION_PROGRESS.json').write_text(json.dumps(rows))
 conn.close();conn=None;assert worker.wait(timeout=60)==0
finally:
 if conn is not None:conn.close()
 if worker is not None and worker.poll() is None:worker.wait(timeout=60)
 log.close();clean=not Path('/var/lib/rml24-fpga-shared-guard/reset_required.json').exists();(root/'NORMALIZATION_RESULT.json').write_text(json.dumps(dict(rows=rows,diagnostic_only=True,truth_not_supplied=True,guard_clean=clean,npu_stop=[line for line in (root/'normalization_npu.log').read_text(errors='replace').splitlines() if 'NPU_STREAM_STOP' in line])))
 if clean:subprocess.run(['systemctl','start','rml24-integrated'],check=True)
 else:raise RuntimeError('guard remains; no forced restart')
print('NORMALIZATION_REPLAY_DONE_BASELINE_RESTORED',len(rows),flush=True)
