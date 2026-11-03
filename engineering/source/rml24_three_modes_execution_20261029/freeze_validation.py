from pathlib import Path
import hashlib,json,subprocess
r=Path('/root/rml24_three_modes_execution_20261029');tree=r/'delivery_progressfix1';out=r/'VALIDATION_FREEZE.json';assert not out.exists()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
expected=json.loads((tree/'evidence/CANDIDATE_SOURCE_IDENTITY.json').read_text())
for rel,h in expected.items():assert sha(tree/rel)==h,rel
compat=json.loads((r/'SUPERVISOR_EOF_COMPAT.json').read_text());assert sha(tree/'scripts/run_candidate_eof_compat.py')==compat['compat_sha']
external={'/root/amr_rescue_20261025/build/npu_stream':'cc88cb0bf5cde766937d011978314b7dafd1122d0f18e1cbda731ec2f7a440d8','/root/amr_rescue_20261025/pluto_link_probe.py':'1b248f8f391976513c35ca54f31d7daef3fa363e2d095940f9ff17d4d60126a2','/root/amr_rescue_20261025/pilot_recovery.py':'d7538a1e27b65cd6b712607b485f1e07de447467bbfdbb04ce67143f9d797713','/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16/rml24_adamrv11_bf16.json':'28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42','/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16/rml24_adamrv11_bf16.raw':'c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151'}
for name,h in external.items():assert sha(Path(name))==h,name
paths=[p for p in tree.rglob('*') if p.is_file() and p.suffix in ['.py','.cpp','.hpp','.sh'] and '__pycache__' not in p.parts];paths.append(tree/'candidate/bin/board_ui_live_rml24_final');files={str(p):sha(p) for p in paths};files.update(external)
obj=dict(status='SHORT_TESTED_CANDIDATE_FROZEN_PENDING_FORMAL_AUTHORIZATION_AND_FINAL_UI_PAGINATION',files=files,root=str(tree),changes=['Supervisor normal EOF race compatibility','Draw progress before NO SIGNAL early return'],no_model_or_rx_algorithm_change=True)
out.write_text(json.dumps(obj,indent=2));print('CANDIDATE_FREEZE_CREATED',len(files),sha(out))
