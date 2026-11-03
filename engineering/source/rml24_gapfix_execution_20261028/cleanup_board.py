import json,os,signal,subprocess,time
from pathlib import Path
r=Path('/root/rml24_gapfix_execution_20261028');stopped=[]
for p in Path('/proc').glob('[0-9]*/cmdline'):
    try:
        args=p.read_bytes().split(b'\0')
        if (b'/root/rml24_gapfix_execution_20261028/candidate/rml24_final/board_runtime/receiver_repeat_mean_gapfix1.py' in args and
            any(v.startswith(str(r).encode()+b'/') for v in args)):
            pid=int(p.parent.name);os.kill(pid,signal.SIGTERM);stopped.append(pid)
    except (FileNotFoundError,PermissionError,ProcessLookupError):pass
for _ in range(12):
    live=[]
    for pid in stopped:
        try:
            if Path('/proc/%d/stat'%pid).read_text().split()[2]!='Z':live.append(pid)
        except FileNotFoundError:pass
    if not live:break
    time.sleep(1)
target='/root/rml24_gapfix_execution_20261028/candidate/bin/board_ui_live_rml24_final'
for p in Path('/proc').glob('[0-9]*/exe'):
    try:
        if os.readlink(str(p))==target:os.kill(int(p.parent.name),signal.SIGTERM)
    except (FileNotFoundError,PermissionError,ProcessLookupError):pass
time.sleep(2)
if subprocess.run(['pgrep','-x','npu_stream'],stdout=subprocess.DEVNULL).returncode==0:
    raise RuntimeError('NPU still running; refuse to start another receiver')
v=subprocess.run(['systemctl','start','rml24-ui','rml24-receiver'],capture_output=True,text=True,timeout=35)
report=dict(stopped_candidate_pids=stopped,baseline_start_returncode=v.returncode,stderr=v.stderr,
     units={u:subprocess.run(['systemctl','is-active',u],capture_output=True,text=True).stdout.strip()
            for u in ['rml24-ui','rml24-receiver']})
(r/'cleanup.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
if v.returncode:raise SystemExit(v.returncode)
