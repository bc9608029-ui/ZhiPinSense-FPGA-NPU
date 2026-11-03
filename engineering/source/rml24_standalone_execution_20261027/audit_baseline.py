import gzip,json,hashlib
from pathlib import Path
r=Path(__file__).parent
e=json.loads(gzip.decompress((r/'board_evidence.json.gz').read_bytes()))
expected={
'/etc/systemd/system/rml24-ui.service':'6ee4461dfae6f1b513e1ae136dc489982ab95318e6aa3b8213654a17e2b8e00e',
'/etc/systemd/system/rml24-receiver.service':'febdfe0940585b56d6725f04fdcad1a8a71b9fd703a3a4bc5fc6493b34229c7e',
'/opt/rml24-system/bin/board_ui_live_rml24_final':'3950201f64f4575755840df2d98879b5d3e44a109372192366d67a90652adaf6',
'/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16/rml24_adamrv11_bf16.json':'28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42',
'/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16/rml24_adamrv11_bf16.raw':'c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151'}
base='/root/rml24_standalone_execution_20261027/candidate/'
for rel in ['rml24_final/board_runtime/standalone_receiver.py','rml24_final/runtime/standalone_control.py',
            'rml24_final/runtime/receiver_core.py','rml24_final/recovery/candidate_two_dc.py']:
    expected[base+rel]=hashlib.sha256((r/'candidate'/rel).read_bytes()).hexdigest()
actual=e['board_source_and_baseline_hashes']
checks=[dict(file=k,expected=v,actual=actual.get(k),passed=actual.get(k)==v) for k,v in expected.items()]
checks.append(dict(check='native_ui_is_aarch64',passed=e['ui_elf_machine']==183))
report=dict(checks=checks,passed=sum(x['passed'] for x in checks),total=len(checks))
(r/'BASELINE_AND_SOURCE_AUDIT.json').write_text(json.dumps(report,indent=2))
print('BASELINE_AND_SOURCE_AUDIT %d/%d'%(report['passed'],report['total']))
for c in checks:
    if not c['passed']:print('MISMATCH',c)
