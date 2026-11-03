from pathlib import Path
import json,time,hashlib,subprocess,sys,datetime
r=Path(__file__).parent;short=Path('E:/FPGA_Work/smartscan_prefetch_fix3_20261031/phase30_final_ui_clock_short');deadline=time.monotonic()+600
while True:
 if (short/'FAILURE.json').exists():raise RuntimeError('Short test failed; no formal retry')
 if (short/'DEVICE_STATUS.json').exists() and json.loads((short/'DEVICE_STATUS.json').read_text())['stage']=='DEVICE_PHASE_ENDED_ORIGINAL_RESTORED':break
 if time.monotonic()>deadline:raise RuntimeError('Short-test cleanup timeout')
 time.sleep(3)
subprocess.run([sys.executable,str(short/'audit_mono.py')],check=True)
receipt=json.loads((short/'UI_TIMING_RF_RECEIPT.json').read_text());assert receipt['correct']==receipt['denominator']==3 and receipt['history_episode_labels'][:3]==[3,4,3] and receipt['history_uptime_valid'] and receipt['receiver_clean']
files=[p for p in r.rglob('*') if p.is_file() and p.suffix in ('.py','.json') and p.name not in ('APPROVAL.json','HELPERS_FREEZE.json')];freeze={p.relative_to(r).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files};(r/'HELPERS_FREEZE.json').write_text(json.dumps(freeze,indent=2),encoding='utf-8')
assert not (r/'APPROVAL.json').exists();approval=dict(allowed=True,scope=['sweep24'],plan_sha256=hashlib.sha256((r/'FORMAL_PLAN.json').read_bytes()).hexdigest(),helpers_sha256=hashlib.sha256((r/'HELPERS_FREEZE.json').read_bytes()).hexdigest(),source='User explicitly asked fix timing and history together then test, subsequently instructed continue testing toward final deployment. Existing fixed/search240 results retained; only invalid-telemetry sweep24 is repeated.',short_receipt_sha256=hashlib.sha256((short/'UI_TIMING_RF_RECEIPT.json').read_bytes()).hexdigest(),recorded=datetime.datetime.now().isoformat());(r/'APPROVAL.json').write_text(json.dumps(approval,indent=2),encoding='utf-8')
print('ACTUAL_SWEEP_PATH_SHORT_PASS_START_ONLY_SWEEP24',flush=True)
subprocess.run([sys.executable,'-u',str(r/'run_formal.py')],check=True)
