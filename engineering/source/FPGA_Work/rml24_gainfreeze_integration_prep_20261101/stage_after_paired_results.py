from pathlib import Path
import json,time,subprocess,sys
p=Path(__file__).parent;previous=p.parent/'rml24_gainfreeze_range_paired_20261101/GAINFREEZE_PAIRED_COVERAGE.json'
for _ in range(700):
 if previous.exists():break
 time.sleep(5)
assert previous.exists();d=json.loads(previous.read_text());manual={x['gain']:x['original_correct'] for x in d if x['mode']=='manual_bw5'};freeze={x['gain']:x['original_correct'] for x in d if x['mode']=='gainfreeze_bw5'};passed=freeze[-40]==24 and freeze[-60]>=manual[-60];(p/'STAGING_DECISION.json').write_text(json.dumps(dict(passed=passed,manual=manual,freeze=freeze),indent=2))
if not passed:print('DO_NOT_STAGE_REGRESSION');raise SystemExit(0)
for name in ['gain_freeze_radio.py','stage_gainfreeze.py']:
 subprocess.run(['powershell','-NoProfile','-File','E:/rml24_three_modes_execution_20261029/upload.ps1','-Local',str(p/name),'-Remote','/root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031/'+name],check=True)
r=subprocess.run(['powershell','-NoProfile','-File','E:/scan_exec_20261027/serial.ps1','-Command','python3 /root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031/stage_gainfreeze.py','-Seconds','5'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT);(p/'STAGING_RESULT.txt').write_bytes(r.stdout);assert r.returncode==0 and b'GAINFREEZE_INTEGRATION_STAGED_NOT_DEPLOYED' in r.stdout;print('CANDIDATE_STAGED_FOR_REVIEW_NOT_DEPLOYED',flush=True)
