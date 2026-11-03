from pathlib import Path
import json,hashlib,subprocess,sys,time,re,gzip,base64,ctypes
p=Path(__file__).parent;sys.path.insert(0,str(p));from timing_contract import first_capture,validate_calibration,validate_records
plan=json.loads((p/'PLAN.json').read_text());auth=json.loads((p/'AUTHORIZATION.json').read_text());assert auth['autonomous_regressions'] and auth['deploy_after_qualified'];results=[];phase='SMOKES';k=ctypes.windll.kernel32;assert k.SetThreadExecutionState(0x80000001)!=0

def status(stage,**fields):(p/'STATUS.json').write_text(json.dumps(dict(stage=stage,not_deployed=True,**fields)))
def ps(argv):
 q=subprocess.run(['powershell','-NoProfile','-File']+argv,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);s=q.stdout.decode('utf8',errors='replace');assert q.returncode==0,s;return s

def board(command,seconds=4):return ps(['E:/FPGA_Work/rml24_lockpilot_formal_prep_20261101/serial_exclusive.ps1','-Command',command,'-Seconds',str(seconds)])
def device(action,name,seconds=4):return board('python3 /root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031/headroom_device.py '+action+' '+name,seconds)
def clock(q,name):
 v=json.loads(ps(['E:/FPGA_Work/rml24_timing_fix_20261031/clock_sync_monotonic.ps1']));(q/name).write_text(json.dumps(v,indent=2));return v

def run_round(run):
 name=run['name'];q=p/name;assert not (q/'START.txt').exists();started=False
 try:
  started=True;t=device('start',name,12);(q/'START.txt').write_text(t);assert re.search(r'(?:^|[\r\n])FORMAL_STARTED '+name,t),t
  for _ in range(20):
   t=device('ready',name,3)
   if re.search(r'(?:^|[\r\n])FORMAL_READY 1',t):break
   time.sleep(2)
  assert re.search(r'(?:^|[\r\n])FORMAL_READY 1',t),t
  before=clock(q,'CLOCK_PRE.json');status('RF_RUNNING',phase=phase,round=name,completed=0,total=run['n'])
  with (q/'TX.log').open('w') as f:
   tx=subprocess.Popen([sys.executable,str(q/'tx_formal.py'),name],stdout=f,stderr=subprocess.STDOUT)
   while tx.poll() is None:
    try:
     text=(q/'TX.log').read_text();m=re.findall(r'TX (\d+)/(\d+)',text);done=int(m[-1][0]) if m else 0;status('RF_RUNNING',phase=phase,round=name,completed=done,total=run['n'])
    except OSError:pass
    time.sleep(3)
   assert tx.returncode==0,(q/'TX.log').read_text()[-1800:]
  after=clock(q,'CLOCK_POST.json')
 finally:
  if started:
   t=device('stop',name,40);(q/'RESTORE.txt').write_text(t);assert re.search(r'(?:^|[\r\n])FORMAL_RESTORED '+name,t),t
 t=device('export',name,50);(q/'EXPORT.txt').write_text(t);m=re.search(r'FORMAL_BEGIN([A-Za-z0-9+/=\s]+)FORMAL_END',t);assert m;data=base64.b64decode(re.sub(r'\s','',m[1]));(q/'EVIDENCE.json.gz').write_bytes(data);v=json.loads(gzip.decompress(data));s=v['supervisor'];f=v['final'];assert s['clean_stop'] and s['stop_errors']==[] and s['rx_restore']==[] and f['restore_errors']==[] and f['ui_failed']==0 and v['guard_clean'] and v['restore']['guard_absent_before_restore'] and v['restore']['health']['ready'];assert f['valid']>0 and v['backend_counts']=={'fpga':f['valid']};assert all(x['repeat_average']==8 for x in v['rows'] if x['finite']);n=f['valid']*8;m=re.search(r'frames=(\d+) apply=(\d+) reset=(\d+) discipline=(\d+)',' '.join(v['npu_stop']));assert m and tuple(map(int,m.groups()))==(n,1,max(0,n-1),1)
 drift=validate_calibration(before,after);validate_records(v['rows'],before);ev=[json.loads(x) for x in (q/(name+'_tx/events_private.jsonl')).read_text().splitlines()];truth=json.loads((q/(name+'_tx/plan_private.json')).read_text());assert len(ev)==len(truth)==run['n'];restore=json.loads((q/(name+'_tx/restore.json')).read_text());assert restore['errors']==[] and all(r['ok'] for r in restore['readback'])
 for i,(a,b) in enumerate(zip(ev,truth)):assert a['index']==i and a['clock_id']=='windows-qpc' and all(a[key]==b[key] for key in ('seq','file','label','source_sha256'))
 selected=first_capture(ev,v['rows'],before['offset_ns'],run['hz'] if run['mode']=='CONTINUOUS_SCAN' else None);rows=[]
 for e,x in zip(ev,selected):
  pred=x['pred'] if x and x['finite'] else -1;freq_ok=True
  if run['mode']=='CONTINUOUS_SCAN' or name=='wide13':freq_ok=bool(x and abs(x['center_hz']-e.get('hz',run['hz']))<=10000)
  rows.append(dict(index=e['index'],expected=e['label'],pred=pred,chosen_frame=x['frame_id'] if x else None,correct=pred==e['label'] and freq_ok,missing=x is None))
 result=dict(name=name,denominator=run['n'],correct=sum(x['correct'] for x in rows),missing=sum(x['missing'] for x in rows),minimum_correct=run['minimum_correct'],clock_drift_ns=drift,rows=rows,candidate_identity_sha256=json.loads((p/'CANDIDATE_META.json').read_text())['identity_sha256']);result['gate_pass']=result['correct']>=result['minimum_correct'] and result['missing']==0;(q/'SCORE.json').write_text(json.dumps(result,indent=2));results.append({key:value for key,value in result.items() if key!='rows'});(p/'RESULTS.json').write_text(json.dumps(results,indent=2));print('ROUND_COMPLETE',json.dumps(results[-1]),flush=True);return result

try:
 for run in plan['runs'][:2]:
  result=run_round(run)
  if not result['gate_pass']:status('SMOKE_GATE_FAILED_BASELINE_RESTORED',round=run['name']);raise SystemExit(2)
 (p/'SMOKE_GATES.json').write_text(json.dumps(dict(all_passed=True,results=results),indent=2));status('SMOKES_PASS_WAITING_FROZEN_CONTINUATION')
 deadline=time.monotonic()+1800
 while not (p/'CONTINUATION_READY.json').exists():
  if time.monotonic()>deadline:raise RuntimeError('continuation package not ready; baseline left restored')
  time.sleep(5)
 frozen=json.loads((p/'CONTINUATION_READY.json').read_text())
 for filename,digest in frozen['files'].items():assert hashlib.sha256((p/filename).read_bytes()).hexdigest()==digest,filename
 # Upload future deployment helper now, while the baseline is restored and no RF child is running.
 ps(['E:/rml24_three_modes_execution_20261029/upload.ps1','-Local',str(p/'software_deploy.py'),'-Remote','/root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031/software_deploy.py'])
 phase='FORMAL_REGRESSION'
 for run in plan['runs'][2:]:run_round(run)
 formal=results[2:];assert len(formal)==4
 if not all(x['gate_pass'] for x in formal):status('FORMAL_GATE_FAILED_BASELINE_RESTORED_NOT_DEPLOYED',results=formal);raise SystemExit(3)
 gates=dict(all_passed=True,candidate_identity_sha256=json.loads((p/'CANDIDATE_META.json').read_text())['identity_sha256'],results=formal,smokes=results[:2],gain_short_score_sha256=hashlib.sha256(Path('E:/FPGA_Work/rml24_gain_only_clipguard_rf_20261101/SCORE.json').read_bytes()).hexdigest(),model_public_bit_unchanged=True);(p/'QUALIFIED_GATES.json').write_text(json.dumps(gates,indent=2));phase='SOFTWARE_DEPLOYMENT';status('ALL_RF_GATES_PASS_DEPLOYMENT_STARTING');subprocess.run([sys.executable,str(p/'deploy_and_verify.py')],check=True);status('QUALIFIED_SOFTWARE_DEPLOYMENT_COMPLETE',deployed_release=json.loads((p/'DEPLOYMENT_RESULT.json').read_text()).get('release'));print('GAIN_ADAPTATION_QUALIFIED_AND_SOFTWARE_DEPLOYED',flush=True)
except SystemExit:raise
except Exception as e:
 status('STOPPED_REVIEW_REQUIRED_BASELINE_RESTORE_CHECK',phase=phase,error=str(e));(p/'FAILURE.json').write_text(json.dumps(dict(phase=phase,error=str(e)),indent=2));raise
finally:k.SetThreadExecutionState(0x80000000)
