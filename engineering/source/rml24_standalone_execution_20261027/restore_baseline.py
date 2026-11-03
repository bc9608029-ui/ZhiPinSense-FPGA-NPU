"""Stop only this round's exact UI executable, then restart unchanged baseline units."""
import json,os,signal,subprocess,time
from pathlib import Path
r=Path('/root/rml24_standalone_execution_20261027')
target=str(r/'candidate/bin/board_ui_live_rml24_final')
if subprocess.run(['pgrep','-x','npu_stream'],stdout=subprocess.DEVNULL).returncode==0:
    raise RuntimeError('NPU still running; refuse overlapping baseline start')
stopped=[]
for p in Path('/proc').glob('[0-9]*/exe'):
    try:
        if os.readlink(str(p))==target:
            pid=int(p.parent.name);os.kill(pid,signal.SIGTERM);stopped.append(pid)
    except (FileNotFoundError,PermissionError,ProcessLookupError):pass
time.sleep(2)
start=subprocess.run(['systemctl','start','rml24-ui','rml24-receiver'],capture_output=True,text=True,timeout=35)
report=dict(candidate_ui_stopped=stopped,start_returncode=start.returncode,start_error=start.stderr,
            units={})
for unit in ['rml24-ui','rml24-receiver']:
    report['units'][unit]={name:subprocess.run(['systemctl',name,unit],capture_output=True,text=True).stdout.strip()
                           for name in ['is-active','is-enabled']}
(r/'baseline_restoration.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report),flush=True)
if start.returncode:raise SystemExit(start.returncode)
