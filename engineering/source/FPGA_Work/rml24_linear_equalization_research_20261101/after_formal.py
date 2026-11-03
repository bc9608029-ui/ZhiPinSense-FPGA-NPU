from pathlib import Path
import time,json,re,subprocess,gzip,base64
p=Path(__file__).parent;formal=Path('E:/FPGA_Work/rml24_lockpilot_formal_prep_20261101');deadline=time.monotonic()+10800
while time.monotonic()<deadline:
 try:
  status=json.loads((formal/'STATUS.json').read_text());monitor=json.loads((formal/'monitoring/FORMAL_MONITOR.json').read_text())
 except (FileNotFoundError,json.JSONDecodeError):time.sleep(20);continue
 if status.get('stage')=='ALL_ROUNDS_COMPLETE_NOT_DEPLOYED':break
 if not monitor['controller_alive']:
  (p/'CHAIN_STATUS.json').write_text(json.dumps(dict(stage='BLOCKED_FORMAL_EARLY_EXIT_NO_DEVICE_ACTION')));raise SystemExit(1)
 time.sleep(20)
else:raise RuntimeError('formal wait timeout; no device action')
v=json.loads(gzip.decompress((formal/'wide13/EVIDENCE.json.gz').read_bytes()));assert v['guard_clean'] and v['restore']['health']['ready'] and v['supervisor']['clean_stop']
def ps(a):
 q=subprocess.run(['powershell','-NoProfile','-File']+a,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);s=q.stdout.decode('utf8',errors='replace');assert q.returncode==0,s;return s
def board(cmd,seconds=3):return ps(['E:/scan_exec_20261027/serial.ps1','-Command',cmd,'-Seconds',str(seconds)])
(p/'CHAIN_STATUS.json').write_text(json.dumps(dict(stage='FORMAL_FINISHED_LINEAR_REPLAY_STARTING',no_new_rf=True)))
(p/'START.txt').write_text(board('nohup /root/miniconda3/envs/torch_v2.0.1_aarch64/bin/python3 /root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031/replay_linear_single.py > /root/linear_single_20261101.log 2>&1 < /dev/null &'))
for _ in range(40):
 t=board('test -f /root/rml24_linear_single_replay_20261101/CLASSIFICATION_RESULT.json && echo LINEAR_REPLAY_DONE',2)
 if re.search(r'(?:^|[\r\n])LINEAR_REPLAY_DONE',t):break
 time.sleep(3)
else:raise RuntimeError('linear replay result absent; inspect logs')
command='python3 -c '+repr('import pathlib,gzip,base64; p=pathlib.Path("/root/rml24_linear_single_replay_20261101/CLASSIFICATION_RESULT.json"); print("LINEAR_BEGIN"+base64.b64encode(gzip.compress(p.read_bytes())).decode()+"LINEAR_END")')
t=board(command,6);(p/'EXPORT.txt').write_text(t);m=re.search(r'(?:^|[\r\n])LINEAR_BEGIN([A-Za-z0-9+/=\s]+)LINEAR_END',t);assert m;v=json.loads(gzip.decompress(base64.b64decode(re.sub(r'\s','',m[1]))));assert v['guard_clean'];(p/'RESULT.json').write_text(json.dumps(v,indent=2));truth={r['index']:r for r in json.loads((p/'MAPPING_PC_ONLY.json').read_text())};original=json.loads(Path('E:/FPGA_Work/rml24_single_repeat_precision_rf_20261101/CLASSIFICATION_RESULT.json').read_text());old={r['index']:r['prediction']['pred'] for r in original['rows']};new={r['index']:r.get('prediction',{}).get('pred',-1) for r in v['rows']};assert set(truth)==set(new)==set(old);rows=[]
for i,t in truth.items():rows.append(dict(t,old_pred=old[i],new_pred=new[i],old_correct=old[i]==t['expected'],new_correct=new[i]==t['expected']))
gained=[r for r in rows if r['new_correct'] and not r['old_correct']];lost=[r for r in rows if r['old_correct'] and not r['new_correct']];result=dict(scope='Same actual1-repeat raw IQ35 captures; offline frozen-NPU replay; not new RF qualification',old_correct=sum(r['old_correct'] for r in rows),new_correct=sum(r['new_correct'] for r in rows),denominator=len(rows),gained=gained,lost=lost,no_paired_regressions=not lost,deployed=False,rows=rows);(p/'SCORE.json').write_text(json.dumps(result,indent=2));health=board('systemctl is-active rml24-integrated; readlink -f /opt/rml24-integrated/current',3);(p/'RESTORED_SERVICE.txt').write_text(health);assert re.search(r'(?:^|[\r\n])active',health);(p/'CHAIN_STATUS.json').write_text(json.dumps(dict(stage='LINEAR_REPLAY_COMPLETE_BASELINE_RESTORED_NOT_DEPLOYED')));print(json.dumps(result),flush=True)
