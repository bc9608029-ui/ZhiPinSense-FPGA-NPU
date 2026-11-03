from pathlib import Path
import subprocess,sys,time,json,re,gzip,base64
p=Path(__file__).parent;out=p/'smoke_pc'
def ps(args):
 r=subprocess.run(['powershell','-NoProfile','-File']+args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);t=r.stdout.decode('utf8',errors='replace');assert r.returncode==0,t;return t
def board(c,seconds=3):return ps(['E:/scan_exec_20261027/serial.ps1','-Command',c,'-Seconds',str(seconds)])
def sync(name):
 d=json.loads(ps(['E:/FPGA_Work/rml24_timing_fix_20261031/clock_sync_monotonic.ps1']));(out/name).write_text(json.dumps(d,indent=2));return d
for _ in range(800):
 d=json.loads((p/'STAGING_DECISION.json').read_text()) if (p/'STAGING_DECISION.json').exists() else None
 if d and not d['passed']:raise SystemExit('STAGING_GATES_FAILED_NO_SMOKE')
 if (p/'STAGING_RESULT.txt').exists() and b'GAINFREEZE_INTEGRATION_STAGED_NOT_DEPLOYED' in (p/'STAGING_RESULT.txt').read_bytes():break
 time.sleep(5)
assert (p/'STAGING_RESULT.txt').exists()
for name in ['start_integrated_smoke.py','restore_after_smoke.py']:
 ps(['E:/rml24_three_modes_execution_20261029/upload.ps1','-Local',str(p/name),'-Remote','/root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031/'+name])
try:
 (out/'START.txt').write_text(board('python3 /root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031/start_integrated_smoke.py'))
 for _ in range(20):
  t=board('grep --color=never STANDALONE_READY /root/rml24_gainfreeze_integration_20261101/smoke_run/rx.log 2>/dev/null')
  if re.search(r'(?:^|[\r\n])STANDALONE_READY ',t):break
  time.sleep(2)
 assert re.search(r'(?:^|[\r\n])STANDALONE_READY ',t),t
 a=sync('CLOCK_PRE.json');subprocess.run([sys.executable,str(out/'tx_paired.py'),'fixed'],stdout=(out/'TX.log').open('w'),stderr=subprocess.STDOUT,check=True);b=sync('CLOCK_POST.json');assert a['board_boot_id']==b['board_boot_id'] and abs(a['offset_ns']-b['offset_ns'])<100000000 and max(a['uncertainty_ns'],b['uncertainty_ns'])<250000000
 q="python3 -c \"import json,gzip,base64;from pathlib import Path;r=[json.loads(x) for x in Path('/root/rml24_gainfreeze_integration_20261101/smoke_run/capture/records.jsonl').read_text().splitlines()];print('DATA_BEGIN'+base64.b64encode(gzip.compress(json.dumps([dict(m=x['capture_monotonic_ns'],ok=x['candidate'].get('finite'),pred=x['candidate'].get('pred')) for x in r]).encode())).decode()+'DATA_END')\"";t=board(q);(out/'EXPORT.txt').write_text(t);m=re.search(r'DATA_BEGIN([A-Za-z0-9+/=\s]+)DATA_END',t);assert m;rows=json.loads(gzip.decompress(base64.b64decode(re.sub(r'\s','',m.group(1)))));ev=json.loads((out/'fixed/VARIABLE_TX_EVENTS.json').read_text());assert len(ev)==24;off=(a['offset_ns']+b['offset_ns'])//2;scores=[]
 for e in ev:
  r=[x for x in rows if e['start_qpc_ns']+1000000000<=x['m']+off<=e['end_qpc_ns']-300000000];x=min(r,key=lambda x:x['m']) if r else None;scores.append(dict(expected=e['class_index'],chosen=x,correct=bool(x and x['ok'] and x['pred']==e['class_index'])))
 d=dict(denominator=24,correct=sum(x['correct'] for x in scores),missing=sum(x['chosen'] is None for x in scores),rows=scores,not_deployed=True);d['gate_pass']=d['correct']==24 and d['missing']==0;(out/'SCORE.json').write_text(json.dumps(d,indent=2));print('INTEGRATED_SMOKE_SCORED',d['correct'],flush=True)
finally:(out/'RESTORE.txt').write_text(board('python3 /root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031/restore_after_smoke.py',20))
