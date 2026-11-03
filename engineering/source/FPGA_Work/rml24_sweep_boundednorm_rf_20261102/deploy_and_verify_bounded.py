from pathlib import Path
import json,subprocess,sys,time,re,gzip,base64,hashlib
p=Path(__file__).parent;sys.path.insert(0,str(p));from timing_contract import first_capture,validate_calibration,validate_records
BASE='/root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031';REMOTE='/root/rml24_sweep_boundednorm_20261102';activated=False

def ps(args):
 q=subprocess.run(['powershell','-NoProfile','-File']+args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);s=q.stdout.decode('utf8',errors='replace');assert q.returncode==0,s;return s
def board(c,seconds=4):return ps(['E:/FPGA_Work/rml24_lockpilot_formal_prep_20261101/serial_exclusive.ps1','-Command',c,'-Seconds',str(seconds)])
def upload(name,remote):return ps(['E:/rml24_three_modes_execution_20261029/upload.ps1','-Local',str(p/name),'-Remote',BASE+'/'+remote])
def action(name,timeout=180):
 text=board('nohup python3 '+BASE+'/software_deploy_bounded.py '+name+' > '+REMOTE+'/'+name+'.log 2>&1 < /dev/null &',2);(p/('DEPLOY_'+name+'_START.txt')).write_text(text);deadline=time.monotonic()+timeout
 while time.monotonic()<deadline:
  command='python3 -c '+repr('import pathlib,json; r=pathlib.Path("'+REMOTE+'"); d=r/"'+name+'_DONE.json"; e=r/"'+name+'_ERROR.json"; print("ACTION_DONE "+json.dumps(json.loads(d.read_text()))) if d.exists() else print("ACTION_ERROR "+e.read_text()) if e.exists() else print("ACTION_PENDING")')
  text=board(command,2);m=re.search(r'(?:^|[\r\n])ACTION_DONE (\{[^\r\n]+\})',text)
  if m:(p/('DEPLOY_'+name+'_DONE.json')).write_text(json.dumps(json.loads(m[1]),indent=2));return json.loads(m[1])
  if re.search(r'(?:^|[\r\n])ACTION_ERROR ',text):raise RuntimeError(text)
  time.sleep(2)
 raise RuntimeError('software action timeout '+name)
def clock(name):
 v=json.loads(ps(['E:/FPGA_Work/rml24_timing_fix_20261031/clock_sync_monotonic.ps1']));(p/'post24'/name).write_text(json.dumps(v,indent=2));return v

user_ready=json.loads((p/'DEPLOYMENT_USER_READY.json').read_text());assert user_ready.get('screen_powered') and user_ready.get('user_authorized_deploy'),'User requested screen power confirmation before deployment'
gates=json.loads((p/'QUALIFIED_GATES.json').read_text());assert gates['all_passed'] and all(x['gate_pass'] for x in gates['results']) and json.loads((p/'AUTHORIZATION.json').read_text())['deploy_after_qualified']
try:
 upload('QUALIFIED_GATES.json','BOUNDED_SWEEP_QUALIFIED_GATES.json');staged=action('stage');active=action('activate');activated=True;before=clock('CLOCK_PRE.json')
 with (p/'post24/TX.log').open('w') as f:subprocess.run([sys.executable,str(p/'post24/tx_formal.py'),'post24'],stdout=f,stderr=subprocess.STDOUT,check=True)
 after=clock('CLOCK_POST.json');sweep_control=action('control_sweep');sweep_before=clock('SWEEP_CLOCK_PRE.json')
 with (p/'postsweep6/TX.log').open('w') as h:subprocess.run([sys.executable,str(p/'postsweep6/tx_formal.py'),'postsweep6'],stdout=h,stderr=subprocess.STDOUT,check=True)
 sweep_after=clock('SWEEP_CLOCK_POST.json');stopped=action('stop_export');text=board('python3 '+BASE+'/software_deploy_bounded.py export',30);(p/'post24/EXPORT.txt').write_text(text);m=re.search(r'DEPLOY_EVIDENCE_BEGIN([A-Za-z0-9+/=\s]+)DEPLOY_EVIDENCE_END',text);assert m;data=base64.b64decode(re.sub(r'\s','',m[1]));(p/'post24/EVIDENCE.json.gz').write_bytes(data);v=json.loads(gzip.decompress(data));s=v['supervisor'];f=v['final'];assert s['clean_stop'] and s['stop_errors']==[] and s['rx_restore']==[] and f['restore_errors']==[] and f['ui_failed']==0 and v['guard_clean'];assert v['backend_counts']=={'fpga':f['valid']};n=f['valid']*8;m=re.search(r'frames=(\d+) apply=(\d+) reset=(\d+) discipline=(\d+)',' '.join(v['npu_stop']));assert m and tuple(map(int,m.groups()))==(n,1,max(0,n-1),1);drift=validate_calibration(before,after);validate_records(v['rows'],before);events=[json.loads(x) for x in (p/'post24/post24_tx/events_private.jsonl').read_text().splitlines()];truth=json.loads((p/'post24/post24_tx/plan_private.json').read_text());assert len(events)==len(truth)==24;restore=json.loads((p/'post24/post24_tx/restore.json').read_text());assert restore['errors']==[] and all(x['ok'] for x in restore['readback'])
 for i,(e,t) in enumerate(zip(events,truth)):assert e['index']==i and e['clock_id']=='windows-qpc' and all(e[k]==t[k] for k in ('seq','file','label','source_sha256'))
 selected=first_capture(events,v['rows'],before['offset_ns']);rows=[dict(index=e['index'],expected=e['label'],pred=x['pred'] if x and x['finite'] else -1,correct=bool(x and x['finite'] and x['pred']==e['label'] and abs(x['center_hz']-2400000000)<=10000),missing=x is None) for e,x in zip(events,selected)];score=dict(correct=sum(r['correct'] for r in rows),denominator=24,missing=sum(r['missing'] for r in rows),clock_drift_ns=drift,rows=rows);(p/'post24/SCORE.json').write_text(json.dumps(score,indent=2));assert score['correct']==24 and score['missing']==0,'post-deployment RF smoke not passed';sweep_events=[json.loads(x) for x in (p/'postsweep6/postsweep6_tx/events_private.jsonl').read_text().splitlines()];sweep_truth=json.loads((p/'postsweep6/postsweep6_tx/plan_private.json').read_text());assert len(sweep_events)==len(sweep_truth)==6
 for index,(e,t) in enumerate(zip(sweep_events,sweep_truth)):assert e['index']==index and e['clock_id']=='windows-qpc' and all(e[key]==t[key] for key in ('seq','file','label','source_sha256'))
 sweep_drift=validate_calibration(sweep_before,sweep_after);sweep_selected=first_capture(sweep_events,v['rows'],sweep_before['offset_ns'],2403600000);sweep_rows=[dict(index=e['index'],expected=e['label'],pred=x['pred'] if x and x['finite'] else -1,correct=bool(x and x['finite'] and x['pred']==e['label'] and abs(x['center_hz']-2403600000)<=10000 and x['mode']=='CONTINUOUS_SCAN'),missing=x is None,calibration=x.get('input_calibration') if x else None) for e,x in zip(sweep_events,sweep_selected)];sweep_score=dict(correct=sum(x['correct'] for x in sweep_rows),denominator=6,missing=sum(x['missing'] for x in sweep_rows),clock_drift_ns=sweep_drift,rows=sweep_rows);(p/'postsweep6/SCORE.json').write_text(json.dumps(sweep_score,indent=2));sweep_restore=json.loads((p/'postsweep6/postsweep6_tx/restore.json').read_text());assert sweep_restore['errors']==[] and all(x['ok'] for x in sweep_restore['readback']);assert sweep_score['correct']==6 and sweep_score['missing']==0 and any(x['calibration'] and x['calibration']['applied'] for x in sweep_rows),'production sweep calibration smoke failed';final=action('final_start');result=dict(post_sweep_rf=sweep_score,deployed=True,release=staged['release'],previous=staged['previous'],software_restart_verified=final['software_restart_verified'],physical_cold_boot_pending=True,health=final['health'],post_rf=score,candidate_identity_sha256=gates['candidate_identity_sha256'],model_bit_public_frame_unchanged=True);(p/'DEPLOYMENT_RESULT.json').write_text(json.dumps(result,indent=2));print('QUALIFIED_GAIN_SOFTWARE_DEPLOYMENT_AND_POST_RF_PASSED',result['release'],flush=True)
except Exception as e:
 error=dict(error=str(e),activated=activated,deployed=False)
 if (p/'DEPLOY_stage_DONE.json').exists():
  try:error['rollback']=action('rollback')
  except Exception as rollback_error:error['rollback_error']=str(rollback_error)
 (p/'DEPLOYMENT_ERROR.json').write_text(json.dumps(error,indent=2));raise
