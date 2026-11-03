from pathlib import Path
import subprocess,sys,time,json,re,gzip,base64
p=Path(__file__).parent;sys.path.insert(0,'E:/FPGA_Work/rml24_gainfreeze_formal_prep_20261101');from timing_contract import first_capture,validate_calibration,validate_records
def ps(a):
 q=subprocess.run(['powershell','-NoProfile','-File']+a,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);t=q.stdout.decode('utf8',errors='replace');assert q.returncode==0,t;return t
def board(c,seconds=4):return ps(['E:/scan_exec_20261027/serial.ps1','-Command',c,'-Seconds',str(seconds)])
def device(action,seconds=4):return board('python3 /root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031/lockpilot_device.py '+action+' smoke24b',seconds)
def clock(name):
 d=json.loads(ps(['E:/FPGA_Work/rml24_timing_fix_20261031/clock_sync_monotonic.ps1']));(p/name).write_text(json.dumps(d,indent=2));return d
started=False
try:
 started=True;t=device('start',12);(p/'START.txt').write_text(t);assert re.search(r'(?:^|[\r\n])FORMAL_STARTED smoke24b',t),t
 for _ in range(20):
  t=device('ready',3)
  if re.search(r'(?:^|[\r\n])FORMAL_READY 1',t):break
  time.sleep(2)
 assert re.search(r'(?:^|[\r\n])FORMAL_READY 1',t),t
 before=clock('CLOCK_PRE.json');(p/'STATUS.json').write_text(json.dumps(dict(stage='SHORT_INTEGRATED_RF_RUNNING',not_deployed=True)))
 with (p/'TX.log').open('w') as f:subprocess.run([sys.executable,str(p/'tx_formal.py'),'smoke24b'],stdout=f,stderr=subprocess.STDOUT,check=True)
 after=clock('CLOCK_POST.json')
finally:
 if started:
  t=device('stop',40);(p/'RESTORE.txt').write_text(t);assert re.search(r'(?:^|[\r\n])FORMAL_RESTORED smoke24b',t),t
text=device('export',35);(p/'EXPORT.txt').write_text(text);m=re.search(r'FORMAL_BEGIN([A-Za-z0-9+/=\s]+)FORMAL_END',text);assert m;v=json.loads(gzip.decompress(base64.b64decode(re.sub(r'\s','',m[1]))));(p/'EVIDENCE.json').write_text(json.dumps(v,indent=2));assert v['supervisor']['clean_stop'] and v['guard_clean'] and v['final']['restore_errors']==[] and v['final']['ui_failed']==0 and v['restore']['health']['ready'];validate_calibration(before,after);validate_records(v['rows'],before);events=[json.loads(x) for x in (p/'smoke24b_tx/events_private.jsonl').read_text().splitlines()];selected=first_capture(events,v['rows'],before['offset_ns']);assert len(events)==24;rows=[dict(index=e['index'],expected=e['label'],pred=x['pred'] if x and x['finite'] else -1,correct=bool(x and x['finite'] and x['pred']==e['label']),missing=x is None) for e,x in zip(events,selected)];result=dict(scope='24 existing source0 waveforms, short integrated search smoke, original TX precision, not formal promotion',correct=sum(x['correct'] for x in rows),denominator=24,missing=sum(x['missing'] for x in rows),rows=rows,not_deployed=True);(p/'SCORE.json').write_text(json.dumps(result,indent=2));(p/'STATUS.json').write_text(json.dumps(dict(stage='SHORT_COMPLETE_BASELINE_RESTORED_NOT_DEPLOYED',correct=result['correct'],missing=result['missing'])));print(json.dumps(result),flush=True)
