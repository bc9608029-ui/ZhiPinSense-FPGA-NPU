import argparse,hashlib,json,subprocess,sys
from pathlib import Path
r=Path('/root/rml24_three_modes_execution_20261029');tree=r/'delivery_progressfix1'
def check():
 p=r/'VALIDATION_FREEZE.json';assert hashlib.sha256(p.read_bytes()).hexdigest()=='ea6715f166145e73fd90ba2f49bb7cd73dadf200666a4ddd8be1c9322bab06ef'
 for name,h in json.loads(p.read_text())['files'].items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h,name
 assert hashlib.sha256((tree/'scripts/run_candidate_finalize_v2.py').read_bytes()).hexdigest()=='302b7588634c71c516825195baf963224adb220962b2c3011864c4c9de4ddb91'
 print('VALIDATION_FREEZE_PASS',flush=True)
p=argparse.ArgumentParser();p.add_argument('name',choices=['formal_sweep24_02']);a=p.parse_args();mode,duration={'formal_fixed01':('FIXED',1120),'formal_lock01':('BAND_SCAN',1610),'formal_sweep24_02':('CONTINUOUS_SCAN',1120)}[a.name];check();active=[]
for u in ['rml24-ui','rml24-receiver']:
 state=subprocess.run(['systemctl','is-active',u],capture_output=True,text=True).stdout.strip()
 if state in ['active','activating']:active.append(u)
(r/(a.name+'_original_units.json')).write_text(json.dumps(active))
common=[sys.executable,str(tree/'scripts/run_candidate_finalize_v2.py'),'--legacy-root','/root/amr_rescue_20261025','--model-dir','/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16','--npu-sha','cc88cb0bf5cde766937d011978314b7dafd1122d0f18e1cbda731ec2f7a440d8']
subprocess.run(common+['--check'],check=True)
try:
 subprocess.run(['systemctl','stop','rml24-receiver','rml24-ui'],check=True)
 if subprocess.run(['pgrep','-x','npu_stream'],stdout=subprocess.DEVNULL).returncode==0:raise RuntimeError('NPU occupied; refuse overlap')
 rc=subprocess.run(common+['--run',str(r/a.name),'--mode',mode,'--duration-sec',str(duration),'--history-file',str(r/'formal_history.txt')]).returncode
 if rc:raise RuntimeError('Supervisor rc='+str(rc))
 check()
finally:
 if subprocess.run(['pgrep','-x','npu_stream'],stdout=subprocess.DEVNULL).returncode==0:raise RuntimeError('NPU still active; restoration withheld')
 for proc in Path('/proc').iterdir():
  if not proc.name.isdigit():continue
  try: args=(proc/'cmdline').read_bytes().split(b'\0')
  except (FileNotFoundError,PermissionError,ProcessLookupError):continue
  if str(r/a.name).encode() in args:raise RuntimeError('Candidate process still active; restoration withheld')
 for u in active:subprocess.run(['systemctl','start',u],check=True)
 (r/(a.name+'_restored_units.json')).write_text(json.dumps({u:subprocess.run(['systemctl','is-active',u],capture_output=True,text=True).stdout.strip() for u in active}));print('FORMAL_ORIGINAL_SERVICES_RESTORED',flush=True)
