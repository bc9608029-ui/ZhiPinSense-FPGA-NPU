from pathlib import Path
import argparse,json,hashlib,subprocess,shutil,time,socket,gzip,base64,collections
BASE=Path('/root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031');ROOT=Path('/root/rml24_sweep_raw_diagnostic_20261101');SOURCE=Path('/root/rml24_gain_headroom_centerfix_20261101/candidate');RUNS={'nominal24':('BAND_SCAN',280),'sweep6':('CONTINUOUS_SCAN',350),'fixed240':('FIXED',1720),'search240':('BAND_SCAN',1720),'sweep24':('CONTINUOUS_SCAN',1200),'wide13':('FIXED',420)}
p=argparse.ArgumentParser();p.add_argument('action',choices=['start','ready','stop','export','tune']);p.add_argument('name',choices=RUNS);p.add_argument('hz',type=int,nargs='?');a=p.parse_args();run=ROOT/'runs'/a.name;unit='rml24-sweep-raw-diagnostic-'+a.name

def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def healthy():
 pid=int(subprocess.check_output(['systemctl','show','rml24-integrated','-p','MainPID','--value']).strip());args=Path('/proc/%d/cmdline'%pid).read_bytes().decode().strip('\0').split('\0');r=Path(args[args.index('--run')+1]);children=json.loads((r/'children.json').read_text());alive={c['role']:Path('/proc/%d/cmdline'%c['pid']).exists() and Path('/proc/%d/cmdline'%c['pid']).read_bytes().decode().strip('\0').split('\0')==list(map(str,c['argv'])) for c in children};logs={k:(r/(k+'.log')).read_text(errors='replace') for k in ('npu','ui','rx')};return dict(ready=all(alive.get(k) for k in ('npu','ui','rx')) and all(t in logs[k] for k,t in [('npu','NPU_STREAM_READY'),('ui','UI_FB_READY'),('rx','STANDALONE_READY')]),run=str(r),alive=alive,release=str(Path('/opt/rml24-integrated/current').resolve()))
if a.action=='start':
 assert sha(SOURCE/'evidence/CANDIDATE_SOURCE_IDENTITY.json')=='bf43d2c52a3d06831496e76d51b7acff7505dc2edb64871008a1043af718a753';expected=json.loads((SOURCE.parent/'STAGING_RESULT.json').read_text())['identity']
 for rel,digest in expected.items():assert sha(SOURCE/rel)==digest,rel
 assert not run.exists();assert shutil.disk_usage('/').free>int(1.2*1024**3);assert 'rml24_pl_sha256=f42dd12f03bf81c65978b7034b45808efd5035f6a358cc54710f2404530a057c' in Path('/proc/cmdline').read_text();run.parent.mkdir(parents=True,exist_ok=True)
 common=['--legacy-root','/root/amr_rescue_20261025','--model-dir','/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16','--npu-sha','cc88cb0bf5cde766937d011978314b7dafd1122d0f18e1cbda731ec2f7a440d8'];py='/root/miniconda3/envs/torch_v2.0.1_aarch64/bin/python3';supervisor=str(SOURCE/'scripts/run_candidate_finalize_v2.py');subprocess.run([py,supervisor]+common+['--check'],check=True);subprocess.run(['systemctl','stop','rml24-integrated'],check=True)
 for cmd in [['pgrep','-x','npu_stream'],['pgrep','-f','^/root/rml24_fpga_shared_owner_20261031/build/npu_stream_shared']]:assert subprocess.run(cmd).returncode==1
 assert not Path('/var/lib/rml24-fpga-shared-guard/reset_required.json').exists();probe=subprocess.check_output(['/root/rml24_fpga_diag_1793380588/scan_xrt','--probe'],universal_newlines=True);assert 'SMARTSCAN_PROBE version=1 idle=1' in probe and 'error=0' in probe
 cmd=['systemd-run','--unit='+unit,'--property=KillMode=mixed','--property=SendSIGKILL=no','--property=TimeoutStopSec=120','--setenv=HOME=/root','--setenv=PATH=/root/miniconda3/envs/torch_v2.0.1_aarch64/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',py,supervisor]+common+['--run',str(run),'--mode',RUNS[a.name][0],'--duration-sec',str(RUNS[a.name][1]),'--history-file',str(ROOT/('formal_history_'+a.name+'.txt')),'--save-captures'];subprocess.run(cmd,check=True);print('FORMAL_STARTED '+a.name,flush=True)
elif a.action=='ready':
 ready=all((run/(k+'.log')).exists() and token in (run/(k+'.log')).read_text(errors='replace') for k,token in [('npu','NPU_STREAM_READY'),('ui','UI_FB_READY'),('rx','STANDALONE_READY')]);print('FORMAL_READY '+str(int(ready)),flush=True)
elif a.action=='tune':
 assert a.name=='wide13' and a.hz is not None;s=socket.socket(socket.AF_UNIX);s.settimeout(40);s.connect(str(run/'control.sock'));f=s.makefile('rwb');f.write(('SET_FIXED_HZ '+str(a.hz)+'\n').encode());f.flush();lines=[]
 while True:
  line=f.readline().decode().strip();lines.append(line)
  if 'accepted' not in line:break
 assert line.startswith('OK') and 'applied_fixed_hz=' in line,lines;actual=int(line.split('applied_fixed_hz=')[1].split()[0]);assert abs(actual-a.hz)<=100;print('FORMAL_TUNED '+str(actual),flush=True)
elif a.action=='stop':
 subprocess.run(['systemctl','stop',unit],check=True);absent=not Path('/var/lib/rml24-fpga-shared-guard/reset_required.json').exists();assert absent,'hardware recovery required; no restart attempted';assert shutil.disk_usage('/').free>1024**3;subprocess.run(['systemctl','start','rml24-integrated'],check=True);health={}
 for _ in range(40):
  try:health=healthy()
  except Exception:health={}
  if health.get('ready'):break
  time.sleep(.5)
 (run/'FORMAL_RESTORE.json').write_text(json.dumps(dict(guard_absent_before_restore=absent,health=health),indent=2));assert health.get('ready'),health;print('FORMAL_RESTORED '+a.name,flush=True)
else:
 rows=[json.loads(x) for x in (run/'capture/records.jsonl').read_text().splitlines()];backend=[json.loads(x) for x in (run/'capture/spectrum_backend.jsonl').read_text().splitlines()];npu=(run/'npu.log').read_text(errors='replace');value=dict(supervisor=json.loads((run/'supervisor.json').read_text()),final=json.loads((run/'capture/final.json').read_text()),restore=json.loads((run/'FORMAL_RESTORE.json').read_text()),backend_counts=dict(collections.Counter(x['backend_used'] for x in backend)),npu_stop=[x for x in npu.splitlines() if 'NPU_STREAM_STOP' in x],guard_clean='HARDWARE_GUARD_CLEAN_EXIT' in npu,rows=[dict(frame_id=x['frame_id'],capture_monotonic_ns=x['capture_monotonic_ns'],clock_id=x['clock_id'],boot_id=x['boot_id'],pred=x['candidate']['pred'],finite=x['candidate']['finite'],repeat_average=x['candidate'].get('repeat_average'),scan_steps=x['scan_steps'],center_hz=x['center_hz'],gain_diagnostic=x.get('gain_diagnostic',{})) for x in rows]);print('FORMAL_BEGIN'+base64.b64encode(gzip.compress(json.dumps(value).encode())).decode()+'FORMAL_END',flush=True)
