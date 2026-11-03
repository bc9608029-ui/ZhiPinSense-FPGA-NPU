from pathlib import Path
import argparse,json,hashlib,subprocess,sys,time,re,base64,gzip,shutil
from timing_contract import first_capture,validate_calibration,validate_records
p=Path(__file__).parent;ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args();plan=json.loads((p/'FORMAL_PLAN.json').read_text());freeze=json.loads((p/'HELPERS_FREEZE.json').read_text())
for name,digest in freeze.items():assert hashlib.sha256((p/name).read_bytes()).hexdigest()==digest,name
assert hashlib.sha256((p/'TRUTH_FROZEN_PC_ONLY.json').read_bytes()).hexdigest()==plan['truth_sha256']
for run in plan['runs']:subprocess.run([sys.executable,str(p/'tx_formal.py'),run['name'],'--check'],check=True)
if args.check:print('PRECHECK_PASS_NO_HARDWARE_APPROVAL_PENDING');raise SystemExit(0)
if not (p/'APPROVAL.json').exists():raise SystemExit('EXPLICIT_APPROVAL_REQUIRED_NO_DEVICE_ACTION')
a=json.loads((p/'APPROVAL.json').read_text());assert a['allowed'] and a['plan_sha256']==hashlib.sha256((p/'FORMAL_PLAN.json').read_bytes()).hexdigest() and a['helpers_sha256']==hashlib.sha256((p/'HELPERS_FREEZE.json').read_bytes()).hexdigest();assert shutil.disk_usage(p).free>2*1024**3

def ps(argv):
 q=subprocess.run(['powershell','-NoProfile','-File']+argv,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);text=q.stdout.decode('utf8',errors='replace');assert q.returncode==0,text;return text
def board(command,seconds=5):return ps(['E:/scan_exec_20261027/serial.ps1','-Command',command,'-Seconds',str(seconds)])
def device(action,name,seconds=5):return board('python3 /root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031/lockpilot_formal_device.py '+action+' '+name,seconds)
def clock(folder,name):
 d=json.loads(ps(['E:/FPGA_Work/rml24_timing_fix_20261031/clock_sync_monotonic.ps1']));(folder/name).write_text(json.dumps(d,indent=2));return d
for name in ['lockpilot_formal_device.py','LOCKPILOT_EXPECTED.json']:ps(['E:/rml24_three_modes_execution_20261029/upload.ps1','-Local',str(p/name),'-Remote','/root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031/'+name])
results=[]
for run in plan['runs']:
 name=run['name'];folder=p/name;folder.mkdir(exist_ok=False);started=False
 try:
  started=True;t=device('start',name,12);(folder/'START.txt').write_text(t);assert re.search(r'(?:^|[\r\n])FORMAL_STARTED '+name,t),t
  for _ in range(20):
   t=device('ready',name,3)
   if re.search(r'(?:^|[\r\n])FORMAL_READY 1',t):break
   time.sleep(2)
  assert re.search(r'(?:^|[\r\n])FORMAL_READY 1',t),t
  before=clock(folder,'CLOCK_PRE.json');(p/'STATUS.json').write_text(json.dumps(dict(stage='FORMAL_RF_RUNNING',round=name)))
  with (folder/'TX.log').open('w') as f:subprocess.run([sys.executable,str(p/'tx_formal.py'),name],stdout=f,stderr=subprocess.STDOUT,check=True)
  after=clock(folder,'CLOCK_POST.json')
 finally:
  if started:
   t=device('stop',name,40);(folder/'RESTORE.txt').write_text(t);assert re.search(r'(?:^|[\r\n])FORMAL_RESTORED '+name,t),t
 t=device('export',name,50);(folder/'EXPORT.txt').write_text(t);m=re.search(r'FORMAL_BEGIN([A-Za-z0-9+/=\s]+)FORMAL_END',t);assert m;tbytes=base64.b64decode(re.sub(r'\s','',m.group(1)));(folder/'EVIDENCE.json.gz').write_bytes(tbytes);v=json.loads(gzip.decompress(tbytes));s=v['supervisor'];f=v['final'];assert s['clean_stop'] and s['stop_errors']==[] and s['rx_restore']==[] and f['restore_errors']==[] and f['ui_failed']==0 and v['guard_clean'] and v['restore']['guard_absent_before_restore'] and v['restore']['health']['ready'];assert f['valid']>0 and v['backend_counts']=={'fpga':f['valid']};assert all(x['repeat_average']==8 for x in v['rows'] if x['finite']);n=f['valid']*8;m=re.search(r'frames=(\d+) apply=(\d+) reset=(\d+) discipline=(\d+)',' '.join(v['npu_stop']));assert m and tuple(map(int,m.groups()))==(n,1,max(0,n-1),1)
 drift=validate_calibration(before,after);validate_records(v['rows'],before);events=[json.loads(x) for x in (p/(name+'_tx/events_private.jsonl')).read_text().splitlines()];truth=json.loads((p/(name+'_tx/plan_private.json')).read_text());assert len(events)==len(truth)==run['n'];restore=json.loads((p/(name+'_tx/restore.json')).read_text());assert restore['errors']==[] and all(x['ok'] for x in restore['readback'])
 for i,(e,t) in enumerate(zip(events,truth)):assert e['index']==i and e['clock_id']=='windows-qpc' and all(e[k]==t[k] for k in ['seq','file','label','source_sha256'])
 selected=first_capture(events,v['rows'],before['offset_ns'],run['hz'] if run['mode']=='CONTINUOUS_SCAN' else None);scores=[]
 for e,x in zip(events,selected):
  pred=x['pred'] if x and x['finite'] else -1;freq_ok=True
  if run['mode']=='CONTINUOUS_SCAN' or name=='wide13':freq_ok=bool(x and abs(x['center_hz']-e.get('hz',run['hz']))<=10000)
  scores.append(dict(index=e['index'],expected=e['label'],pred=pred,chosen_frame=x['frame_id'] if x else None,correct=pred==e['label'] and freq_ok,missing=x is None))
 result=dict(name=name,denominator=run['n'],correct=sum(x['correct'] for x in scores),missing=sum(x['missing'] for x in scores),minimum_correct=run['minimum_correct'],clock_drift_ns=drift,rows=scores);result['promotion_gate_pass']=result['correct']>=run['minimum_correct'] and result['missing']==0;(folder/'SCORE.json').write_text(json.dumps(result,indent=2));results.append({k:v for k,v in result.items() if k!='rows'});(p/'RESULTS.json').write_text(json.dumps(results,indent=2))
(p/'STATUS.json').write_text(json.dumps(dict(stage='ALL_ROUNDS_COMPLETE_NOT_DEPLOYED',all_accuracy_gates=all(x['promotion_gate_pass'] for x in results))));print('ALL_ROUNDS_COMPLETE_NOT_DEPLOYED')
