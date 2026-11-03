from pathlib import Path
import time,subprocess,sys,json,re
p=Path('E:/FPGA_Work/rml24_weak_adaptive_rf_20261101');src=Path(__file__).parent
for _ in range(300):
 if (p/'ADAPTATION_COVERAGE.json').exists():break
 time.sleep(5)
assert (p/'ADAPTATION_COVERAGE.json').exists()
for name in ['repeat_consistency.py','evaluate_repeat_identity.py']:
 subprocess.run(['powershell','-NoProfile','-File','E:/rml24_three_modes_execution_20261029/upload.ps1','-Local',str(src/name),'-Remote','/root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031/'+name],check=True)
r=subprocess.run(['powershell','-NoProfile','-File','E:/scan_exec_20261027/serial.ps1','-Command','nohup /root/miniconda3/envs/torch_v2.0.1_aarch64/bin/python3 /root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031/evaluate_repeat_identity.py > /root/rml24_repeat_identity.log 2>&1 < /dev/null &','-Seconds','2'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT);(p/'IDENTITY_GATE_START.txt').write_bytes(r.stdout);assert r.returncode==0
print('NEXT_READONLY_RESEARCH_STARTED',flush=True)
