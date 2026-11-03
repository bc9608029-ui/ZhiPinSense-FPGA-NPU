from pathlib import Path
import sys,os,time,json,hashlib,subprocess,re,gzip,base64,shutil,ctypes
r=Path(__file__).parent;p=r.parent;sys.path.insert(0,str(r));from timing_contract import first_capture,validate_calibration,validate_records
k=ctypes.windll.kernel32;assert k.SetThreadExecutionState(0x80000001)!=0;phase='RF';started=False

def ps(argv):
 q=subprocess.run(['powershell','-NoProfile','-File']+argv,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);t=q.stdout.decode('utf8',errors='replace');assert q.returncode==0,t;return t

def board(command,seconds=4):return ps([str(p/'serial_exclusive.ps1'),'-Command',command,'-Seconds',str(seconds)])
def device(action,seconds=4):return board('python3 /root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031/lockpilot_retry_device.py '+action+' wide13',seconds)
def clock(name):
 d=json.loads(ps(['E:/FPGA_Work/rml24_timing_fix_20261031/clock_sync_monotonic.ps1']));(r/name).write_text(json.dumps(d,indent=2));return d
try:
 approval=json.loads((p/'APPROVAL.json').read_text());assert approval['allowed'] and approval['plan_sha256']==hashlib.sha256((p/'FORMAL_PLAN.json').read_bytes()).hexdigest() and approval['helpers_sha256']==hashlib.sha256((p/'HELPERS_FREEZE.json').read_bytes()).hexdigest()
 for name,digest in json.loads((p/'HELPERS_FREEZE.json').read_text()).items():assert hashlib.sha256((p/name).read_bytes()).hexdigest()==digest,name
 contract=json.loads((r/'RETRY_CONTRACT.json').read_text())
 for name,digest in contract['files'].items():assert hashlib.sha256((r/name).read_bytes()).hexdigest()==digest,name
 monitor=p/'monitoring';preserved=monitor/'attempt_a_preserved';preserved.mkdir(exist_ok=True)
 for f in list(monitor.iterdir()):
  if f.is_file():shutil.copyfile(f,preserved/f.name)
 (monitor/'FORMAL_CONTROLLER_PID.txt').write_text(str(os.getpid()))
 (p/'STATUS.json').write_text(json.dumps(dict(stage='FORMAL_RF_RUNNING',round='wide13',attempt='retry1_after_zero_item_serial_abort')))
 for name in ('monitor.py','audit_progress.py'):subprocess.Popen([sys.executable,str(monitor/name)],stdout=(r/(name+'.log')).open('w'),stderr=subprocess.STDOUT)
 try:
  started=True;t=device('start',12);(r/'START.txt').write_text(t);assert re.search(r'(?:^|[\r\n])FORMAL_STARTED wide13',t),t
  for _ in range(20):
   t=device('ready',3)
   if re.search(r'(?:^|[\r\n])FORMAL_READY 1',t):break
   time.sleep(2)
  assert re.search(r'(?:^|[\r\n])FORMAL_READY 1',t),t
  before=clock('CLOCK_PRE.json')
  with (r/'TX.log').open('w') as f:subprocess.run([sys.executable,str(r/'tx_formal.py'),'wide13'],stdout=f,stderr=subprocess.STDOUT,check=True)
  after=clock('CLOCK_POST.json')
 finally:
  if started:
   t=device('stop',40);(r/'RESTORE.txt').write_text(t);assert re.search(r'(?:^|[\r\n])FORMAL_RESTORED wide13',t),t
 t=device('export',40);(r/'EXPORT.txt').write_text(t);m=re.search(r'FORMAL_BEGIN([A-Za-z0-9+/=\s]+)FORMAL_END',t);assert m;compressed=base64.b64decode(re.sub(r'\s','',m[1]));(r/'EVIDENCE.json.gz').write_bytes(compressed);v=json.loads(gzip.decompress(compressed));s=v['supervisor'];f=v['final'];assert s['clean_stop'] and s['stop_errors']==[] and s['rx_restore']==[] and f['restore_errors']==[] and f['ui_failed']==0 and v['guard_clean'] and v['restore']['guard_absent_before_restore'] and v['restore']['health']['ready'];assert f['valid']>0 and v['backend_counts']=={'fpga':f['valid']};assert all(x['repeat_average']==8 for x in v['rows'] if x['finite']);n=f['valid']*8;m=re.search(r'frames=(\d+) apply=(\d+) reset=(\d+) discipline=(\d+)',' '.join(v['npu_stop']));assert m and tuple(map(int,m.groups()))==(n,1,max(0,n-1),1)
 drift=validate_calibration(before,after);validate_records(v['rows'],before);events=[json.loads(x) for x in (r/'wide13_tx/events_private.jsonl').read_text().splitlines()];truth=json.loads((r/'wide13_tx/plan_private.json').read_text());assert len(events)==len(truth)==13;restore=json.loads((r/'wide13_tx/restore.json').read_text());assert restore['errors']==[] and all(x['ok'] for x in restore['readback'])
 for i,(e,t) in enumerate(zip(events,truth)):assert e['index']==i and e['clock_id']=='windows-qpc' and all(e[a]==t[a] for a in ('seq','file','label','source_sha256'))
 selected=first_capture(events,v['rows'],before['offset_ns']);scores=[]
 for e,x in zip(events,selected):
  pred=x['pred'] if x and x['finite'] else -1;freq_ok=bool(x and abs(x['center_hz']-e['hz'])<=10000);scores.append(dict(index=e['index'],expected=e['label'],pred=pred,chosen_frame=x['frame_id'] if x else None,correct=pred==e['label'] and freq_ok,missing=x is None))
 result=dict(name='wide13',denominator=13,correct=sum(x['correct'] for x in scores),missing=sum(x['missing'] for x in scores),minimum_correct=13,clock_drift_ns=drift,rows=scores,attempt='retry1_after_serial_abort_before_any_scored_item');result['promotion_gate_pass']=result['correct']==13 and result['missing']==0;(r/'SCORE.json').write_text(json.dumps(result,indent=2))
 # Preserve original failed attempts; canonical paths now identify the complete retry explicitly.
 for name in ('START.txt','TX.log','CLOCK_PRE.json','CLOCK_POST.json','RESTORE.txt','EXPORT.txt','EVIDENCE.json.gz','SCORE.json'):shutil.copyfile(r/name,p/'wide13'/name)
 shutil.copytree(r/'wide13_tx',p/'wide13_tx',dirs_exist_ok=True)
 results=json.loads((p/'RESULTS.json').read_text());assert len(results)==3;results.append({a:b for a,b in result.items() if a!='rows'});(p/'RESULTS.json').write_text(json.dumps(results,indent=2));(p/'STATUS.json').write_text(json.dumps(dict(stage='ALL_ROUNDS_COMPLETE_NOT_DEPLOYED',all_accuracy_gates=all(x['promotion_gate_pass'] for x in results),instrumentation_abort_preserved=True)));print('FOUR_ROUNDS_COMPLETE',json.dumps(results),flush=True)
 phase='POST_RESEARCH';linear=Path('E:/FPGA_Work/rml24_linear_equalization_research_20261101');subprocess.run([sys.executable,str(linear/'after_formal.py')],check=True)
 phase='PACKAGE';subprocess.run([sys.executable,'E:/FPGA_Work/rml24_adaptation_research_20261101/package_after_research.py'],check=True);(r/'CHAIN_COMPLETE.json').write_text(json.dumps(dict(stage='FOUR_ROUNDS_AND_POST_RESEARCH_AND_PACKAGE_COMPLETE',not_deployed=True)));print('ALL_AUTHORIZED_WORK_CHAIN_COMPLETE_NOT_DEPLOYED',flush=True)
except Exception as e:
 (r/'FAILURE.json').write_text(json.dumps(dict(phase=phase,error=str(e)),indent=2))
 if phase=='RF':(p/'STATUS.json').write_text(json.dumps(dict(stage='RF_RETRY_STOPPED_REVIEW_REQUIRED',round='wide13',error=str(e),not_deployed=True)))
 raise
finally:k.SetThreadExecutionState(0x80000000)
