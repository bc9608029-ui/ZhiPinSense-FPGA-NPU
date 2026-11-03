import hashlib,json,re,subprocess,sys,time,datetime
from pathlib import Path
r=Path(__file__).parent;serial=r.parent/'scan_exec_20261027/serial.ps1';root='/root/rml24_three_modes_execution_20261029';tx=r.parent/'rml24_standalone_execution_20261027/autonomous_tx.py'
def status(**v):
 v['updated_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();(r/'FORMAL_RETRY_PROGRESS.json').write_text(json.dumps(v,indent=2));print(json.dumps(v),flush=True)
def board(cmd,seconds=3):
 q=subprocess.run(['powershell','-NoProfile','-File',str(serial),'-Command',cmd,'-Seconds',str(seconds)],capture_output=True);s=q.stdout.decode(errors='replace');(r/'formal_retry_serial_transcript.log').open('a',encoding='utf-8').write(s+'\n');q.check_returncode();return re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',s)
def local_check():
 for rel,h in json.loads((r/'FORMAL_HELPERS_FREEZE.json').read_text()).items():assert hashlib.sha256((r/rel).read_bytes()).hexdigest()==h,rel
 frozen=json.loads((r.parent/'rml24_standalone_execution_20261027/RF_SOURCE_FREEZE.json').read_text())
 for name in ['autonomous_tx.py','scoring_core.py']:assert hashlib.sha256((tx.parent/name).read_bytes()).hexdigest()==frozen[name]
 assert (r/'FORMAL_APPROVAL.json').exists() and (r/'PAGINATION_ACCEPTED.json').exists()
local_check();status(phase='preflight')
for name,mode,hz,hold,n in [('formal_sweep24_02','CONTINUOUS_SCAN',2403600000,40,24)]:
 local_check();q=subprocess.run(['powershell','-NoProfile','-File',str(tx.parent/'clock_sync.ps1')],capture_output=True);q.check_returncode();clock=json.loads(q.stdout.decode(errors='replace'));assert clock['uncertainty_ms']<=250;(r/(name+'_clock.json')).write_text(json.dumps(clock,indent=2))
 status(phase='starting_rx',run=name,total=n)
 board('nohup /root/miniconda3/envs/torch_v2.0.1_aarch64/bin/python3 '+root+'/run_formal_round_board_v2.py '+name+' > '+root+'/'+name+'_driver.log 2>&1 < /dev/null & echo FORMAL_DRIVER_PID=$!')
 ready=False
 for _ in range(15):
  s=board('test -f '+root+'/'+name+'/rx.log && grep -a "^STANDALONE_READY" '+root+'/'+name+'/rx.log; tail -2 '+root+'/'+name+'_driver.log')
  if any(x.startswith('STANDALONE_READY no_tcp=1') for x in s.splitlines()):ready=True;break
  time.sleep(1)
 if not ready:status(phase='error',error='RX not ready',run=name);raise RuntimeError('RX not ready')
 status(phase='transmitting',run=name,completed=0,total=n)
 with (r/(name+'_tx_console.log')).open('wb') as log:
  process=subprocess.Popen([sys.executable,'-u',str(tx),'--out',str(r/(name+'_tx')),'--mode','smoke24' if n==24 else 'formal240','--center-hz',str(hz),'--hold-sec',str(hold),'--warmup-sec','40'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
  for line in process.stdout:
   log.write(line);log.flush();s=line.decode(errors='replace').strip();print(s,flush=True);m=re.search(r'TX index=(\d+)',s)
   if m:status(phase='transmitting',run=name,completed=int(m[1])+1,total=n)
  assert process.wait()==0,'TX failed'
 status(phase='waiting_for_rx_cleanup',run=name,completed=n,total=n)
 finished=False
 for _ in range(35):
  s=board('test -f '+root+'/'+name+'_restored_units.json && echo ROUND_RESTORED; tail -2 '+root+'/'+name+'_driver.log')
  if 'ROUND_RESTORED' in s.splitlines():finished=True;break
  time.sleep(2)
 assert finished,'Missing RX final/restore'
 subprocess.run(['powershell','-NoProfile','-File',str(r/'collect_formal_v2.ps1')],check=True);subprocess.run([sys.executable,str(r/'score_formal_v2.py'),name],check=True);result=json.loads((r/(name+'_score.json')).read_text());status(phase='round_complete',run=name,correct=result['correct'],denominator=n,missing=result['missing'])
local_check();status(phase='sweep_retry_complete_pending_final_audit')
