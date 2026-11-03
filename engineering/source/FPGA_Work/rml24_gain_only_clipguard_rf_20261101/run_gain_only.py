import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
from pathlib import Path
import sys,time,json,subprocess,re,base64,gzip,hashlib,ctypes
p=Path(__file__).parent;sys.path.insert(0,'E:/FPGA_Work/rml24_lockpilot_formal_prep_20261101');from timing_contract import pc_monotonic_ns,validate_calibration
sys.path.insert(0,'E:/FPGA_Work/rml24_range_expansion_20261101/pc/console/vendor');import pluto_link_probe as link;import pilot_recovery as public;from frame_builder import build_frame as golden_frame
from experimental_frame import build_frame
plan=json.loads((p/'PLAN.json').read_text());truth=json.loads((p/'PRIVATE_PLAN.json').read_text());assets=Path('E:/FPGA_Work/rml24_tx_console_integration_20261031/console/assets')
for row in truth:
 data=(assets/row['file']).read_bytes();assert hashlib.sha256(data).hexdigest()==row['source_sha256'];a=build_frame(data,public.train,public.tail,8);b=golden_frame(data,public.train,public.tail);assert a.tobytes()==b.tobytes()

def ps(args):
 q=subprocess.run(['powershell','-NoProfile','-File']+args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);s=q.stdout.decode('utf8',errors='replace');assert q.returncode==0,s;return s
def board(cmd,seconds=3):return ps(['E:/FPGA_Work/rml24_lockpilot_formal_prep_20261101/serial_exclusive.ps1','-Command',cmd,'-Seconds',str(seconds)])
def status(stage,**extra):(p/'STATUS.json').write_text(json.dumps(dict(stage=stage,not_deployed=True,**extra)))
def sync(name):
 v=json.loads(ps(['E:/FPGA_Work/rml24_timing_fix_20261031/clock_sync_monotonic.ps1']));(p/name).write_text(json.dumps(v,indent=2));return v
def export(remote,tag,name):
 command='python3 -c '+repr('import pathlib,gzip,base64; p=pathlib.Path("'+remote+'"); print("'+tag+'_BEGIN"+base64.b64encode(gzip.compress(p.read_bytes())).decode()+"'+tag+'_END")');s=board(command,9);(p/(name+'_SERIAL.txt')).write_text(s);m=re.search(r'(?:^|[\r\n])'+tag+r'_BEGIN([A-Za-z0-9+/=\s]+)'+tag+'_END',s);assert m,s[-1000:];v=json.loads(gzip.decompress(base64.b64decode(re.sub(r'\s','',m[1]))));(p/(name+'.json')).write_text(json.dumps(v,indent=2));return v
k=ctypes.windll.kernel32;assert k.SetThreadExecutionState(0x80000001)!=0;radio=None;buffer=None;events=[];snapshots=[]
try:
 before=sync('CLOCK_PRE.json');status('STARTING_GAIN_ONLY_CAPTURE')
 (p/'START.txt').write_text(board('nohup /root/miniconda3/envs/torch_v2.0.1_aarch64/bin/python3 /root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031/capture_gain_only.py > /root/gain_only_capture_20261101.log 2>&1 < /dev/null &'))
 time.sleep(8);t=board('test -f /root/rml24_gain_only_clipguard_rf_20261101/PROGRESS.json && echo GAIN_CAPTURE_READY; tail -c 300 /root/gain_only_capture_20261101.log');(p/'READY.txt').write_text(t);assert re.search(r'(?:^|[\r\n])GAIN_CAPTURE_READY',t),t
 uris=link.scan_usb();assert len(uris)==1;radio=link.Radio(uris[0])
 try:
  for role,key,value in [('tx','hardwaregain',-40),('tx','sampling_frequency',2560000),('tx','rf_bandwidth',18000000),('tlo','frequency',2403600000),('tlo','powerdown',0)]:
   ch=getattr(radio,role);snapshots.append((role,key,radio.get(ch,key).split()[0]));radio.set(ch,key,value)
  status('GAIN_ONLY_RF_RUNNING',completed=0,total=len(truth))
  with (p/'EVENTS_PC_ONLY.jsonl').open('w') as log:
   for row in truth:
    rc=link.writeattr(radio.tx,b'hardwaregain',str(row['tx_gain_db']).encode());assert rc>=0;actual=float(radio.get(radio.tx,'hardwaregain').split()[0]);assert abs(actual-row['tx_gain_db'])<.01
    buffer=radio.send(build_frame((assets/row['file']).read_bytes(),public.train,public.tail,8));start=pc_monotonic_ns();time.sleep(plan['hold_sec']);radio.stop(buffer);buffer=None;e=dict(row,start_mono_ns=start,end_mono_ns=pc_monotonic_ns());events.append(e);log.write(json.dumps(e)+'\n');log.flush();status('GAIN_ONLY_RF_RUNNING',completed=len(events),total=len(truth));print('GAIN_TX',len(events),'/',len(truth),flush=True);time.sleep(plan['gap_sec'])
 finally:
  if buffer is not None:radio.stop(buffer);buffer=None
  errors=radio.close() or [];radio=None;checks=[];observer=link.Radio(uris[0])
  try:
   for role,key,expected in snapshots:
    actual=observer.get(getattr(observer,role),key).split()[0];checks.append(dict(role=role,key=key,expected=expected,actual=actual,ok=abs(float(actual)-float(expected))<=(.01 if key=='hardwaregain' else 100 if key=='frequency' else 1)))
  finally:errors.extend(observer.close() or [])
  (p/'TX_RESTORE.json').write_text(json.dumps(dict(errors=errors,readback=checks),indent=2));assert errors==[] and all(c['ok'] for c in checks)
 status('RF_COMPLETE_WAITING_CAPTURE_RESTORE',completed=len(events),total=len(truth))
 for _ in range(50):
  t=board('test -f /root/rml24_gain_only_clipguard_rf_20261101/RESULT.json && echo GAIN_CAPTURE_FINISHED; tail -c 200 /root/gain_only_capture_20261101.log',2)
  if re.search(r'(?:^|[\r\n])GAIN_CAPTURE_FINISHED',t):break
  time.sleep(3)
 else:raise RuntimeError('capture completion absent')
 (p/'CAPTURE_FINISH.txt').write_text(t);after=sync('CLOCK_POST.json');drift=validate_calibration(before,after);captures=export('/root/rml24_gain_only_clipguard_rf_20261101/RESULT.json','GAIN_CAPTURE','CAPTURE');assert captures['restore_errors']==[] and captures['guard_clear_before_restore'] and captures['restored_health']['ready'] and captures['boot_id']==before['board_boot_id']
 selected=[]
 for e in events:
  rs=[r for r in captures['rows'] if e['start_mono_ns']+1500000000<=r['initial_mono_ns']+before['offset_ns'] and r['final_mono_ns']+before['offset_ns']<=e['end_mono_ns']-300000000];selected.append(dict(event=e,pair_index=min(rs,key=lambda r:r['initial_mono_ns'])['index'] if rs else None))
 (p/'SELECTED_PC_ONLY.json').write_text(json.dumps(selected,indent=2));indices=sorted(set(r['pair_index'] for r in selected if r['pair_index'] is not None));assert indices;(p/'GAIN_PAIR_REQUEST.json').write_text(json.dumps(dict(indices=indices)));ps(['E:/rml24_three_modes_execution_20261029/upload.ps1','-Local',str(p/'GAIN_PAIR_REQUEST.json'),'-Remote','/root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031/GAIN_PAIR_REQUEST.json'])
 status('FROZEN_MODEL_PAIRED_REPLAY_RUNNING',selected=len(indices),total=len(events));(p/'CLASS_START.txt').write_text(board('nohup /root/miniconda3/envs/torch_v2.0.1_aarch64/bin/python3 /root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031/classify_gain_pairs.py > /root/gain_pair_model_20261101.log 2>&1 < /dev/null &'))
 for _ in range(60):
  t=board('test -f /root/rml24_gain_only_clipguard_rf_20261101/CLASSIFICATION_RESULT.json && echo GAIN_MODEL_FINISHED; tail -c 200 /root/gain_pair_model_20261101.log',2)
  if re.search(r'(?:^|[\r\n])GAIN_MODEL_FINISHED',t):break
  time.sleep(3)
 else:raise RuntimeError('paired model replay absent')
 result=export('/root/rml24_gain_only_clipguard_rf_20261101/CLASSIFICATION_RESULT.json','GAIN_MODEL','MODEL');assert result['guard_clean'];pred={r['index']:r for r in result['rows']};capture_map={r['index']:r for r in captures['rows']};rows=[]
 for s in selected:
  e=s['event'];i=s['pair_index'];pair=pred.get(i,{});cap=capture_map.get(i,{})
  def correct(role):return bool(pair.get(role,{}).get('recovered') and pair[role]['prediction']['pred']==e['label'])
  rows.append(dict(index=e['index'],file=e['file'],expected=e['label'],tx_gain_db=e['tx_gain_db'],pair_index=i,missing=i is None,old_correct=correct('initial'),new_correct=correct('final') and cap.get('headroom_resolved',False),old_pred=pair.get('initial',{}).get('prediction',{}).get('pred',-1),new_pred=pair.get('final',{}).get('prediction',{}).get('pred',-1),initial_gain=cap.get('initial_gain'),final_gain_db=cap.get('final_gain_db'),initial_stats=cap.get('initial_stats'),final_stats=cap.get('final_stats'),backoff_steps=cap.get('backoff_steps',[])))
 assert len(rows)==48;groups=[dict(tx_gain_db=g,denominator=len([x for x in rows if x['tx_gain_db']==g]),old_correct=sum(x['old_correct'] for x in rows if x['tx_gain_db']==g),new_correct=sum(x['new_correct'] for x in rows if x['tx_gain_db']==g)) for g in (-60,-40,-30)];lost=[x for x in rows if x['old_correct'] and not x['new_correct']];gained=[x for x in rows if x['new_correct'] and not x['old_correct']];score=dict(scope='48-item same-TX paired capture study, original8 repeats and TX quantization; not full regression or deployment',clock_drift_ns=drift,denominator=48,old_correct=sum(x['old_correct'] for x in rows),new_correct=sum(x['new_correct'] for x in rows),missing=sum(x['missing'] for x in rows),groups=groups,gained=gained,lost=lost,rows=rows);score['short_no_regression_gate']=not lost and score['missing']==0 and all(g['new_correct']>=g['old_correct'] for g in groups);(p/'SCORE.json').write_text(json.dumps(score,indent=2))
 for _ in range(30):
  t=board('python3 /root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031/gain_health.py',2);m=re.search(r'(?:^|[\r\n])GAIN_HEALTH (\{[^\r\n]+\})',t)
  if m and json.loads(m[1]).get('ready'):break
  time.sleep(1)
 else:raise RuntimeError('baseline not healthy after replay')
 (p/'FINAL_RESTORE.txt').write_text(t);status('GAIN_ONLY_SHORT_COMPLETE_BASELINE_RESTORED',short_gate=score['short_no_regression_gate'],old_correct=score['old_correct'],new_correct=score['new_correct']);print('GAIN_ONLY_SHORT_COMPLETE',json.dumps(groups),'LOSSES',len(lost),'GAINS',len(gained),flush=True)
except Exception as e:status('FAILED_REVIEW_REQUIRED',error=str(e));raise
finally:k.SetThreadExecutionState(0x80000000)
