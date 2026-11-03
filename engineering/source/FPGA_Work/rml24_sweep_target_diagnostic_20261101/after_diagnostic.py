from pathlib import Path
import json,time,subprocess,sys
p=Path(__file__).parent
for _ in range(120):
 try:state=json.loads((p/'STATUS.json').read_text())
 except Exception:state={}
 if state.get('stage')=='RAW_DIAGNOSTIC_COMPLETE_BASELINE_RESTORED':break
 if state.get('stage')=='DIAGNOSTIC_ERROR':raise RuntimeError(state)
 time.sleep(5)
else:raise RuntimeError('diagnostic did not finish; no device access attempted')
time.sleep(5)
q=subprocess.run(['powershell','-NoProfile','-File','E:/rml24_three_modes_execution_20261029/upload.ps1','-Local',str(p/'archive_sweep_target.py'),'-Remote','/root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031/archive_sweep_target.py'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT);(p/'ARCHIVE_UPLOAD.txt').write_bytes(q.stdout);assert q.returncode==0
subprocess.run([sys.executable,str(p/'transfer_sweep_raw.py')],check=True)
print('DIAGNOSTIC_TRANSFER_COMPLETE',flush=True)
