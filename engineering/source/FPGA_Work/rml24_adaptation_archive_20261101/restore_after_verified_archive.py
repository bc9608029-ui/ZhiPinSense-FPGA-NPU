from pathlib import Path
import subprocess,time,json
p=Path(__file__).parent
for _ in range(180):
 if (p/'VERIFIED.json').exists():break
 time.sleep(5)
assert (p/'VERIFIED.json').exists()
for local,remote in [('VERIFIED.json','ARCHIVE_PC_VERIFIED.json'),('cleanup_verified_and_restore.py','cleanup_verified_and_restore.py')]:
 subprocess.run(['powershell','-NoProfile','-File','E:/rml24_three_modes_execution_20261029/upload.ps1','-Local',str(p/local),'-Remote','/root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031/'+remote],check=True)
r=subprocess.run(['powershell','-NoProfile','-File','E:/scan_exec_20261027/serial.ps1','-Command','python3 /root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031/cleanup_verified_and_restore.py','-Seconds','25'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT);(p/'CLEANUP_AND_RESTORE.txt').write_bytes(r.stdout);assert r.returncode==0 and b'RESTORED_FORMAL_READY' in r.stdout;print('VERIFIED_ARCHIVE_CLEANUP_AND_FORMAL_RESTORE_COMPLETE',flush=True)
