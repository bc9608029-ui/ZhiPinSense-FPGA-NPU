import hashlib,json,tarfile,zipfile
from pathlib import Path
r=Path(__file__).parent
model=r/'frozen_dependencies';model.mkdir(exist_ok=True)
archive=r.parent/'rml24_fpga_execution_20261027/baseline_backup/runtime_before.tar.gz'
with tarfile.open(archive) as t:
    for name in ['rml24_adamrv11_bf16.json','rml24_adamrv11_bf16.raw']:
        member='root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16/'+name
        (model/name).write_bytes(t.extractfile(member).read())
expected={'rml24_adamrv11_bf16.json':'28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42',
          'rml24_adamrv11_bf16.raw':'c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151'}
for name,sha in expected.items():
    if hashlib.sha256((model/name).read_bytes()).hexdigest()!=sha:raise RuntimeError('Model mismatch')
files=[r/'repeat_mean_candidate.py',r/'receiver_repeat_mean_v1.py',r/'run_repeat_mean_v1.sh',r/'strict_promotion_gate.py',
       model/'rml24_adamrv11_bf16.json',model/'rml24_adamrv11_bf16.raw',
       r.parent/'rml24_standalone_execution_20261027/candidate/rml24_final/recovery/candidate_two_dc.py',
       r.parent/'rml24_standalone_execution_20261027/candidate/rml24_final/runtime/receiver_core.py']
obj=dict(status='FROZEN_DEVELOPMENT_CANDIDATE_PENDING_EXPLICIT_USER_RF_APPROVAL',
         model_changed=False,public_frame_changed=False,development_only=True,
         protocol_assumption='Eight identical 1024-sample payload repetitions',
         files=[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size) for p in files])
(r/'CANDIDATE_FREEZE.json').write_text(json.dumps(obj,indent=2),encoding='utf-8')
print('CANDIDATE_FROZEN files=%d no_formal_RF_started=1'%len(files))
