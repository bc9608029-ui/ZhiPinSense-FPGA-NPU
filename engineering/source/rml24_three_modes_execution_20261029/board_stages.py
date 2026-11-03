from pathlib import Path
import zipfile,hashlib,subprocess,json,os
r=Path('/root/rml24_three_modes_execution_20261029');p=r/'candidate.zip';events=[];active=[]
def note(stage,**v):
 events.append(dict(stage=stage,**v));(r/'PROGRESS.json').write_text(json.dumps(events,indent=2));print(stage,v,flush=True)
def run(cmd,log,cwd=None):
 with (r/log).open('w') as f:v=subprocess.run(cmd,cwd=cwd,stdout=f,stderr=subprocess.STDOUT)
 if v.returncode:raise RuntimeError('Failed '+log+' rc='+str(v.returncode))
try:
 assert hashlib.sha256(p.read_bytes()).hexdigest()=='19724dc5c1360fb4add86825bfc016b362fcbd47bdc68eda3e051d33e97a8173'
 tree=r/'delivery';tree.mkdir(exist_ok=False)
 with zipfile.ZipFile(p) as z:
  for m in z.infolist():(tree/m.filename).resolve().relative_to(tree.resolve())
  z.extractall(tree)
 checks=(tree/'SHA256SUMS.txt').read_text().splitlines();assert len(checks)==187
 for line in checks:
  h,n=line.split(None,1);assert hashlib.sha256((tree/n.lstrip('* ')).read_bytes()).hexdigest()==h
 note('package_187_verified')
 for u in ['rml24-ui','rml24-receiver']:
  if subprocess.run(['systemctl','is-active','--quiet',u]).returncode==0:active.append(u)
 (r/'original_active_units.json').write_text(json.dumps(active))
 run(['systemctl','cat','rml24-ui','rml24-receiver'],'original_units.log')
 note('building')
 run(['taskset','-c','0','bash','candidate/board_package/build_ui_live_rml24_final.sh'],'build.log',str(tree))
 assert (tree/'candidate/bin/board_ui_live_rml24_final').is_file()
 run(['file',str(tree/'candidate/bin/board_ui_live_rml24_final')],'binary_identity.log')
 note('build_pass')
 py='/root/miniconda3/envs/torch_v2.0.1_aarch64/bin/python3'
 common=[py,str(tree/'scripts/run_candidate.py'),'--legacy-root','/root/amr_rescue_20261025','--model-dir','/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16','--npu-sha','cc88cb0bf5cde766937d011978314b7dafd1122d0f18e1cbda731ec2f7a440d8']
 run(common+['--check'],'strict_preflight.log');note('strict_preflight_pass')
 subprocess.run(['systemctl','stop','rml24-receiver','rml24-ui'],check=True)
 try:
  for mode,name in [('FIXED','quiet_fixed01'),('BAND_SCAN','quiet_lock01'),('CONTINUOUS_SCAN','quiet_sweep01')]:
   note('quiet_test_start',mode=mode)
   run(common+['--run',str(r/name),'--mode',mode,'--duration-sec','60','--history-file',str(r/'candidate_history.txt')],name+'_driver.log')
   report=json.loads((r/name/'supervisor.json').read_text())
   if report.get('stop_errors'):raise RuntimeError('Supervisor stop errors')
   note('quiet_test_complete',mode=mode,supervisor=report)
 finally:
  if subprocess.run(['pgrep','-x','npu_stream'],stdout=subprocess.DEVNULL).returncode==0:raise RuntimeError('NPU still running: restore withheld')
  for u in active:subprocess.run(['systemctl','start',u],check=True)
 note('quiet_tests_complete_physical_ui_and_rf_pending')
except Exception as exc:note('error',error=repr(exc));raise
