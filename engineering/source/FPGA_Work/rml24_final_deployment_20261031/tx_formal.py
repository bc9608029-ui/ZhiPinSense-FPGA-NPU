from pathlib import Path
import argparse,json,hashlib,sys,time,signal
p=argparse.ArgumentParser();p.add_argument('name');p.add_argument('--check',action='store_true');a=p.parse_args();r=Path(__file__).parent;plan=json.loads((r/'FORMAL_PLAN.json').read_text());run=next(x for x in plan['runs'] if x['name']==a.name);truth=json.loads((r/'TRUTH_FROZEN_PC_ONLY.json').read_text());assets=Path('E:/FPGA_Work/rml24_tx_console_integration_20261031/console/assets')
if run['n']==24:
 seen=set();truth=[x for x in truth if x['label'] not in seen and not seen.add(x['label'])]
assert len(truth)==run['n']
for x in truth:assert hashlib.sha256((assets/x['file']).read_bytes()).hexdigest()==x['source_sha256']
if a.check:print('TX_SOURCE_CHECK PASS '+a.name);sys.exit(0)
approval=json.loads((r/'APPROVAL.json').read_text());assert approval['plan_sha256']==hashlib.sha256((r/'FORMAL_PLAN.json').read_bytes()).hexdigest() and approval['allowed']
sys.path.insert(0,'E:/scan_exec_20261027');from ui_interactive_tx import build_frame
sys.path.insert(0,'E:/AMR_Rescue_20261025');import pluto_link_probe as link;import pilot_recovery as public
out=r/(a.name+'_tx');out.mkdir(exist_ok=False);(out/'plan_private.json').write_text(json.dumps(truth,indent=2));stop=[False]
for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:stop.__setitem__(0,True))
def wait(seconds):
 until=time.monotonic()+seconds
 while time.monotonic()<until:
  if stop[0] or (r/'STOP.request').exists():raise RuntimeError('test stopped')
  time.sleep(min(.05,max(0,until-time.monotonic())))
uris=link.scan_usb();assert len(uris)==1,uris;radio=link.Radio(uris[0]);buffer=None;snapshots=[];errors=[];checks=[]
try:
 for role,key,value in [('tx','hardwaregain',-40),('tx','sampling_frequency',2560000),('tx','rf_bandwidth',18000000),('tlo','frequency',run['hz']),('tlo','powerdown',0)]:
  ch=getattr(radio,role);snapshots.append((role,key,radio.get(ch,key).split()[0]));radio.set(ch,key,value);assert abs(float(radio.get(ch,key).split()[0])-value)<=(.01 if key=='hardwaregain' else .5)
 wait(plan['mute_sec']);buffer=radio.send(build_frame((assets/truth[0]['file']).read_bytes(),public.train,public.tail));wait(plan['warmup_sec']);radio.stop(buffer);buffer=None
 with (out/'events_private.jsonl').open('w') as log:
  for i,row in enumerate(truth):
   buffer=radio.send(build_frame((assets/row['file']).read_bytes(),public.train,public.tail));start=time.time_ns();wait(run['hold']);radio.stop(buffer);buffer=None;end=time.time_ns();record=dict(row,index=i,start_ns=start,end_ns=end);log.write(json.dumps(record)+'\n');log.flush();print('TX %d/%d'%(i+1,len(truth)),flush=True);wait(plan['gap_sec'])
 wait(plan['mute_sec'])
finally:
 if buffer is not None:
  try:radio.stop(buffer)
  except Exception as exc:errors.append('stop: '+str(exc))
 try:errors.extend(radio.close() or [])
 except Exception as exc:errors.append('restore: '+str(exc))
 if not errors:
  observer=link.Radio(uris[0])
  try:
   for role,key,expected in snapshots:
    actual=observer.get(getattr(observer,role),key).split()[0];ok=abs(float(actual)-float(expected))<=(.01 if key=='hardwaregain' else .5);checks.append(dict(role=role,key=key,expected=expected,actual=actual,ok=ok))
    if not ok:errors.append('restore mismatch '+role+'.'+key)
  finally:errors.extend(observer.close() or [])
 (out/'restore.json').write_text(json.dumps(dict(errors=errors,readback=checks),indent=2))
assert not errors;print('TX_COMPLETE',flush=True)
