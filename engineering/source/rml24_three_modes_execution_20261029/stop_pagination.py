from pathlib import Path
import os,signal,time,json
r=Path('/root/rml24_three_modes_execution_20261029');entry=str(r/'delivery_progressfix1/scripts/run_candidate_eof_compat.py').encode();run=str(r/'pagination_ui01').encode()
for p in Path('/proc').glob('[0-9]*/cmdline'):
 try:
  args=p.read_bytes().split(b'\0')
  if entry in args and run in args:os.kill(int(p.parent.name),signal.SIGTERM)
 except (FileNotFoundError,PermissionError,ProcessLookupError):pass
for _ in range(60):
 if 'ORIGINAL_SERVICES_RESTORED' in (r/'pagination_ui_driver.log').read_text(errors='replace'):break
 time.sleep(1)
else:raise RuntimeError('Await original service restoration')
s=json.loads((r/'pagination_ui01/supervisor.json').read_text());assert s['stop_errors']==[] and s['rx_restore']==[];print(json.dumps(s));print('UI_TEST_CLEANUP_CONFIRMED')
