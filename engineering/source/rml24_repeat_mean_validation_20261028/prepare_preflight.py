import json
from pathlib import Path
r=Path(__file__).parent
manifest=json.loads((r.parent/'rml24_mainchain_diagnostic_20261028/CANDIDATE_FREEZE.json').read_text())
base='/root/rml24_standalone_execution_20261027/candidate/rml24_final'
mapping={
'repeat_mean_candidate.py':'/root/rml24_mainchain_diagnostic_20261028/repeat_mean_candidate.py',
'receiver_repeat_mean_v1.py':'/root/rml24_mainchain_diagnostic_20261028/receiver_repeat_mean_v1.py',
'run_repeat_mean_v1.sh':base+'/board_runtime/run_repeat_mean_v1.sh',
'rml24_adamrv11_bf16.json':'/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16/rml24_adamrv11_bf16.json',
'rml24_adamrv11_bf16.raw':'/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16/rml24_adamrv11_bf16.raw',
'candidate_two_dc.py':base+'/recovery/candidate_two_dc.py','receiver_core.py':base+'/runtime/receiver_core.py'}
expected={mapping[Path(f['path']).name]:f['sha256'] for f in manifest['files'] if Path(f['path']).name in mapping}
expected[base+'/board_runtime/standalone_receiver.py']='4448eda5b943ed2f883631f938cd7dfa94bbcc660494ff34d0d9463ffa0ff85e'
text='''import hashlib,json
from pathlib import Path
expected=EXPECTED
base=Path("/root/rml24_standalone_execution_20261027/candidate/rml24_final")
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for name,value in expected.items():
    if sha(Path(name))!=value:raise RuntimeError("Frozen board SHA mismatch "+name)
paths=set(Path(n) for n in expected)
for directory in [base/'board_runtime',base/'runtime',base/'recovery']:
    paths.update(directory.glob('*.py'))
paths.update([Path('/root/amr_rescue_20261025/pluto_link_probe.py'),Path('/root/amr_rescue_20261025/pilot_recovery.py'),Path('/root/amr_rescue_20261025/build/npu_stream')])
closure={str(p):sha(p) for p in paths}
report=Path('/root/rml24_repeat_mean_validation_20261028/runtime_closure.json')
if report.exists() and json.loads(report.read_text())!=closure:raise RuntimeError('Runtime closure changed during validation')
report.write_text(json.dumps(closure,indent=2))
print('BOARD_FROZEN_PREFLIGHT_PASS',flush=True)
'''.replace('EXPECTED',repr(expected))
(r/'preflight_board.py').write_bytes(text.encode('utf-8'))
