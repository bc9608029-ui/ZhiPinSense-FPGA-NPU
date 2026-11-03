import hashlib,json
from pathlib import Path
expected={'/root/rml24_mainchain_diagnostic_20261028/repeat_mean_candidate.py': '1e837d42485ce717023b580918773f9f53c3095ab3c4f2870321bd58ebd0bdde', '/root/rml24_mainchain_diagnostic_20261028/receiver_repeat_mean_v1.py': 'ee8bd436cd919ee69b5323fa16dac5a957e9bdf7fb569a4a665fe3fc00f569ca', '/root/rml24_standalone_execution_20261027/candidate/rml24_final/board_runtime/run_repeat_mean_v1.sh': '842dde9ed473b84a09a2766d9910a7087a7adeddfdb8c061c4ac00b97c5c8022', '/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16/rml24_adamrv11_bf16.json': '28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42', '/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16/rml24_adamrv11_bf16.raw': 'c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151', '/root/rml24_standalone_execution_20261027/candidate/rml24_final/recovery/candidate_two_dc.py': 'e0aa12029e9c5aa670a9340d9c078814b10dcfb0ee82c580adaad4f55affcf3a', '/root/rml24_standalone_execution_20261027/candidate/rml24_final/runtime/receiver_core.py': 'cb529824a80e9fa2aea6aaa31375c8d560f117c36b9644862cb459f6c39cd79a', '/root/rml24_standalone_execution_20261027/candidate/rml24_final/board_runtime/standalone_receiver.py': '4448eda5b943ed2f883631f938cd7dfa94bbcc660494ff34d0d9463ffa0ff85e'}
base=Path("/root/rml24_gapfix_execution_20261028/candidate/rml24_final")
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for name,value in expected.items():
    if sha(Path(name))!=value:raise RuntimeError("Frozen board SHA mismatch "+name)
paths=set(Path(n) for n in expected)
paths.update((base.parent/'bin').glob('board_ui_live_rml24_final'))
paths.update((base.parent/'board_package').glob('*.hpp'))
paths.update((base.parent/'board_package').glob('*.cpp'))
paths.update((base.parent/'ui_sw').glob('*.cpp'))
paths.update((base.parent/'ui_sw').glob('*.hpp'))
for directory in [base/'board_runtime',base/'runtime',base/'recovery']:
    paths.update(directory.glob('*.py'))
paths.update([Path('/root/amr_rescue_20261025/pluto_link_probe.py'),Path('/root/amr_rescue_20261025/pilot_recovery.py'),Path('/root/amr_rescue_20261025/build/npu_stream')])
closure={str(p):sha(p) for p in paths}
report=Path('/root/rml24_gapfix_execution_20261028/runtime_closure.json')
if report.exists() and json.loads(report.read_text())!=closure:raise RuntimeError('Runtime closure changed during validation')
report.write_text(json.dumps(closure,indent=2))
print('BOARD_FROZEN_PREFLIGHT_PASS',flush=True)
