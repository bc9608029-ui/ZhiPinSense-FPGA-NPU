"""Replay every valid development capture with one class-independent candidate."""
import hashlib,json,socket,sys
from pathlib import Path
import numpy as np
r=Path('/root/rml24_mainchain_diagnostic_20261028')
sys.path.insert(0,'/root/rml24_standalone_execution_20261027/candidate/rml24_final/board_runtime')
from rml24_dualmode_receiver_centered_v2 import infer
out=r/'gmsk_rms_replay03';records=[json.loads(x) for x in (r/'diag_gmsk02/capture/records.jsonl').read_text().splitlines()]
s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);s.settimeout(20);s.connect(str(out/'npu.sock'))
results=[]
try:
    for row in records:
        if not row['candidate']['finite']:continue
        path=r/'diag_gmsk02/evidence'/('%06d.inputs.bin'%row['frame_id']);data=path.read_bytes()
        sha=hashlib.sha256(data).hexdigest()
        if sha!=row['candidate']['input_sha256']:raise RuntimeError('Source tensor SHA mismatch')
        tensor=np.frombuffer(data,dtype='<f4').reshape(8,2,1024)
        mean=tensor.mean(axis=0,dtype=np.float64).astype('<f4')
        rms=float(np.sqrt(np.mean(mean.astype(np.float64)**2)*2)); mean=(mean/max(rms,1e-12)).astype('<f4'); candidate=np.repeat(mean[None,:,:],8,axis=0)
        result=infer(s,candidate)
        energy=float(np.mean(tensor.astype(np.float64)**2));mean_energy=float(np.mean(mean.astype(np.float64)**2))
        v=dict(frame_id=row['frame_id'],source_input_sha256=sha,
               candidate_input_sha256=hashlib.sha256(candidate.tobytes()).hexdigest(),
               repeat_coherence=mean_energy/max(energy,1e-30),result=result)
        results.append(v)
        if len(results)%50==0:print('DEVELOPMENT_MEAN_REPLAY n=%d'%len(results),flush=True)
finally:
    s.close();(out/'results.json').write_text(json.dumps(results,indent=2))
print('DEVELOPMENT_MEAN_REPLAY_COMPLETE n=%d'%len(results),flush=True)

print(json.dumps(dict(pred_histogram={str(k):sum(v["result"]["pred"]==k for v in results) for k in sorted(set(v["result"]["pred"] for v in results))})),flush=True)
