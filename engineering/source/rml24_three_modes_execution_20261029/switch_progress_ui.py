from pathlib import Path
import os,signal,time,json
r=Path('/root/rml24_three_modes_execution_20261029');target=str(r/'delivery/scripts/run_candidate_eof_compat.py').encode();run=str(r/'ui_accept02').encode()
for p in Path('/proc').glob('[0-9]*/cmdline'):
 try:
  args=p.read_bytes().split(b'\0')
  if target in args and run in args:os.kill(int(p.parent.name),signal.SIGTERM);print('STOP_REQUESTED',p.parent.name)
 except (FileNotFoundError,PermissionError,ProcessLookupError):pass
for _ in range(60):
 log=(r/'ui_accept02_driver.log').read_text(errors='replace')
 if 'ORIGINAL_SERVICES_RESTORED' in log:break
 time.sleep(1)
else:raise RuntimeError('Previous UI supervisor/restore not complete')
report=json.loads((r/'ui_accept02/supervisor.json').read_text());assert report['stop_errors']==[] and report['rx_restore']==[]
s=(r/'run_ui_accept02.py').read_text().replace('ui_accept02','ui_progress03').replace('UI_ACCEPT02_RESULTS.json','UI_PROGRESS03_RESULTS.json').replace('delivery/scripts/run_candidate_eof_compat.py','delivery_progressfix1/scripts/run_candidate_eof_compat.py').replace("[('FIXED','ui_progress03')]","[('CONTINUOUS_SCAN','ui_progress03')]")
(r/'run_ui_progress03.py').write_text(s);print('READY_FOR_PROGRESS_UI')
