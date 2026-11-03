"""Authorized independent RF parameter execution; logs/status persist on F drive.
No Flash writes, FPGA programming or production installation.
"""
import datetime,hashlib,importlib.util,json,os,shlex,subprocess,sys,time,traceback,threading,queue
from pathlib import Path

HERE=Path(__file__).resolve().parent
PREP=HERE.parent/'rml24_test_readiness_20261030'
HOST='root@192.168.126.49'
KEY=Path(os.environ['USERPROFILE'])/'.ssh/rml24_test_20261030_ed25519'
SSH=['C:/Windows/System32/OpenSSH/ssh.exe','-i',str(KEY),'-o','IdentitiesOnly=yes','-o','BatchMode=yes',
     '-o','ConnectTimeout=8','-o','StrictHostKeyChecking=yes',HOST]
SCP=['C:/Windows/System32/OpenSSH/scp.exe','-i',str(KEY),'-o','IdentitiesOnly=yes','-o','BatchMode=yes',
     '-o','ConnectTimeout=8','-o','StrictHostKeyChecking=yes']
ENV=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1')

def write(p,data):
 temp=p.with_suffix('.tmp');temp.write_text(json.dumps(data,indent=2,allow_nan=False),encoding='utf8');os.replace(temp,p)
def status(stage,**data):
 write(HERE/'STATUS.json',dict(stage=stage,time=datetime.datetime.now().astimezone().isoformat(),pid=os.getpid(),**data))
 print(stage,json.dumps(data),flush=True)
def run(args,log=None,input=None,timeout=120,check=True):
 try:r=subprocess.run(args,input=input,capture_output=True,text=True,encoding='utf8',errors='replace',env=ENV,timeout=timeout)
 except subprocess.TimeoutExpired as e:
  text=lambda v:v.decode('utf8',errors='replace') if isinstance(v,bytes) else (v or '')
  if log:log.write_text(text(e.stdout)+text(e.stderr)+'\nCOMMAND_TIMEOUT\n',encoding='utf8')
  raise
 if log:log.write_text(r.stdout+r.stderr,encoding='utf8')
 if check and r.returncode:raise RuntimeError('command failed rc=%d: %s'%(r.returncode,(r.stderr+r.stdout)[-1800:]))
 return r
def remote(cmd,**kwargs):return run([*SSH,cmd],**kwargs)
def pyremote(code,args=(),**kwargs):return remote('python3 - '+shlex.join([str(x) for x in args]),input=code,**kwargs)
def local(script,*args,log=None,timeout=120,check=True):return run([sys.executable,'-I',str(PREP/script),*map(str,args)],log=log,timeout=timeout,check=check)
def pull(remote_path,local_path):run([*SCP,HOST+':'+remote_path,str(local_path)],timeout=120)
def push(local_path,remote_path):run([*SCP,str(local_path),HOST+':'+remote_path],timeout=120)

PROBE=r'''
from pathlib import Path
import subprocess,json,hashlib,importlib.util,shutil
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
root=Path('/root/rml24_parameter_test_root.txt').read_text().strip()
assert root.startswith('/root/rml24_test_setup_') and root.endswith('/rml24_test_readiness_20261030')
python=None
for p in ['/usr/bin/python3','/root/miniconda3/envs/torch_v2.0.1_aarch64/bin/python3','/root/miniconda3/bin/python3']:
 if Path(p).is_file():
  r=subprocess.run([p,'-c','import numpy,scipy'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  if r.returncode==0:python=p;break
assert python,'no numpy/scipy Python'
radio=Path('/root/amr_rescue_20261025/pluto_link_probe.py')
assert sha(radio)=='1b248f8f391976513c35ca54f31d7daef3fa363e2d095940f9ff17d4d60126a2'
npu=Path('/root/amr_rescue_20261025/build/npu_stream');assert npu.is_file()
models=[];recoveries=[]
for base in [Path('/opt/rml24-system'),Path('/root/amr_rescue_20261025'),Path('/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16')]:
 for p in base.rglob('rml24_adamrv11_bf16.json'):
  raw=p.with_suffix('.raw')
  if raw.is_file() and sha(p)=='28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42' and sha(raw)=='c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151':models.append(str(p.parent))
 for p in base.rglob('candidate_two_dc.py'):
  if sha(p)=='e0aa12029e9c5aa670a9340d9c078814b10dcfb0ee82c580adaad4f55affcf3a':recoveries.append(str(p))
assert models and recoveries,'frozen model/recovery not found under deployed roots'
scan="import importlib.util,json; s=importlib.util.spec_from_file_location('r',"+repr(str(radio))+"); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); print(json.dumps(m.scan_usb()))"
uris=json.loads(subprocess.check_output([python,'-c',scan],universal_newlines=True));assert len(uris)==1,uris
state=subprocess.check_output(['systemctl','show','rml24-receiver.service','--property=ActiveState','--value'],universal_newlines=True).strip()
print(json.dumps(dict(root=root,python=python,radio=str(radio),npu=str(npu),model=models[0],recovery=recoveries[0],rx_uri=uris[0],receiver_original_state=state,receiver_was_active=state in ('active','activating','reloading'),free_bytes=shutil.disk_usage('/root').free,npu_sha=sha(npu))))
'''

def clock(path):
 samples=[];q=queue.Queue()
 code="import sys,time\nprint('READY',flush=True)\nfor line in sys.stdin:\n print(time.time_ns(),flush=True)"
 proc=subprocess.Popen([*SSH,'python3 -u -c '+shlex.quote(code)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf8',bufsize=1,env=ENV)
 def reader():
  for line in proc.stdout:q.put(line.strip())
 threading.Thread(target=reader,daemon=True).start()
 try:
  if q.get(timeout=20)!='READY':raise RuntimeError('clock observer did not initialize')
  for _ in range(7):
   before=time.time_ns();proc.stdin.write('T\n');proc.stdin.flush();board=int(q.get(timeout=5));after=time.time_ns()
   samples.append(dict(pc_before_ns=before,pc_after_ns=after,board_ns=board,lo_ns=board-after,hi_ns=board-before))
 finally:
  proc.stdin.close()
  try:proc.wait(timeout=5)
  except subprocess.TimeoutExpired:proc.terminate();proc.wait(timeout=5)
 lo=max(s['lo_ns'] for s in samples);hi=min(s['hi_ns'] for s in samples)
 if hi<lo or hi-lo>200_000_000:raise RuntimeError('clock uncertainty exceeds experiment bound')
 write(path,dict(kind='BOARD_MINUS_PC_CLOCK_BOUND',lo_ns=lo,hi_ns=hi,samples=samples))

def start_rx(info,out,seconds,mode,gain):
 args=[info['python'],'-I',info['root']+'/parameter_rx.py','--radio',info['radio'],'--rx-uri',info['rx_uri'],
       '--out',out,'--mode',mode,'--seconds',str(seconds)]
 if gain is not None:args+=['--gain',str(gain)]
 script="import subprocess,json; p=subprocess.Popen("+repr(args)+",stdin=subprocess.DEVNULL,stdout=open("+repr(out+'.log')+",'w'),stderr=subprocess.STDOUT,start_new_session=True); print(json.dumps({'pid':p.pid}))"
 return json.loads(pyremote(script).stdout)['pid']

def experiment(info,remote_base,label,gain,count):
 folder=HERE/label;folder.mkdir(exist_ok=False);mode='slow_attack' if gain is None else 'manual'
 clock(folder/'clock_pre.json')
 start=time.time_ns()+30_000_000_000
 local('parameter_plan.py','--start-pc-ns',start,'--out',folder/'plan.json','--count-per-class',count,log=folder/'plan.log')
 duration=24*count*6;rxout=remote_base+'/'+label
 pid=start_rx(info,rxout,duration+45,mode,gain)
 write(folder/'rx_process.json',dict(pid=pid,out=rxout))
 status('PARAMETER_RF_RUNNING',arm=label,opportunities=24*count,rx_pid=pid,tx_starts_pc_ns=start)
 txlog=(folder/'tx_process.log').open('w',encoding='utf8')
 tx=subprocess.Popen([sys.executable,'-I',str(PREP/'parameter_tx.py'),'--plan',str(folder/'plan.json'),
                      '--out',str(folder/'tx'),'--tx-uri',info['tx_uri'],
                      '--libiio-library','D:/radioconda/Library/bin/libiio.dll','--transmit'],
                      stdout=txlog,stderr=subprocess.STDOUT,env=ENV)
 try:
  txrc=tx.wait(timeout=duration+75)
 finally:txlog.close()
 if txrc:raise RuntimeError('TX failed; inspect '+str(folder/'tx_process.log'))
 # Wait until the RX process has completed and independent restoration readback exists.
 deadline=time.monotonic()+90
 while True:
  r=remote('test -f '+shlex.quote(rxout+'/restore_readback.json'),check=False)
  if r.returncode==0:break
  if time.monotonic()>deadline:
   pull(rxout+'.log',folder/'rx_process.log');raise RuntimeError('RX failed/incomplete; inspect log')
  time.sleep(2)
 clock(folder/'clock_post.json')
 for name in ['captures.jsonl','capture_summary.json','restore_readback.json']:
  pull(rxout+'/'+name,folder/name)
 pull(rxout+'.log',folder/'rx_process.log')
 args=['--plan',folder/'plan.json','--captures',folder/'captures.jsonl','--tx-events',folder/'tx/tx_events.jsonl',
       '--clock-pre',folder/'clock_pre.json','--clock-post',folder/'clock_post.json']
 local('select_opportunities.py',*args,'--out',folder/'selection.json',log=folder/'selection.log')
 selection=rxout+'_selection.json';push(folder/'selection.json',selection)
 replay=rxout+'_replay'
 status('PARAMETER_NPU_REPLAY',arm=label)
 remote(shlex.join(['bash',info['root']+'/run_parameter_replay.sh',info['python'],info['npu'],info['model'],
                   info['recovery'],rxout,replay,selection]),timeout=3600,log=folder/'npu_replay.log')
 pull(replay+'/replay/replay.jsonl',folder/'replay.jsonl');pull(replay+'/npu.log',folder/'npu.log')
 result=local('parameter_score.py',*args,'--replays',folder/'replay.jsonl',
              '--capture-summary',folder/'capture_summary.json','--rx-restore',folder/'restore_readback.json',
              '--tx-restore',folder/'tx/tx_restore.json','--out',folder/'score.json',log=folder/'score.log',check=False)
 if result.returncode:raise RuntimeError('Measurement invalid; inspect '+str(folder/'score.json'))
 score=json.loads((folder/'score.json').read_text());status('PARAMETER_ARM_COMPLETE',arm=label,correct=score['correct'],denominator=score['denominator'])
 return score

def main():
 status('READ_ONLY_PREFLIGHT')
 info=json.loads(pyremote(PROBE,timeout=120).stdout.strip().splitlines()[-1]);write(HERE/'board_preflight.json',info)
 local('preflight.py',log=HERE/'pc_preflight.log')
 remote(shlex.join([info['python'],'-I',info['root']+'/preflight.py','--model-dir',info['model'],
                    '--recovery',info['recovery'],'--radio',info['radio'],'--npu-bin',info['npu']]),log=HERE/'board_preflight.log')
 # Enumerate TX without creating a radio context.
 os.environ['LIBIIO_LIBRARY']='D:/radioconda/Library/bin/libiio.dll'
 handle=os.add_dll_directory('D:/radioconda/Library/bin')
 spec=importlib.util.spec_from_file_location('tx_probe',PREP/'tx/vendor/pluto_link_probe.py');link=importlib.util.module_from_spec(spec);spec.loader.exec_module(link)
 uris=link.scan_usb()
 if len(uris)!=1:raise RuntimeError('expected one PC TX SDR: '+str(uris))
 info['tx_uri']=uris[0];write(HERE/'board_preflight.json',info)
 base='/root/rml24_param_exec_'+str(int(time.time()));remote('mkdir '+shlex.quote(base));write(HERE/'remote_root.json',dict(root=base))
 stopped=False;restore={};scores={}
 try:
  remote('systemctl stop rml24-receiver.service');stopped=True
  # Do not kill unidentified standalone SDR/NPU processes.
  r=remote("ps -eo pid,args | grep -E '(^|/)(npu_stream|standalone_receiver.py)' | grep -v grep",check=False)
  if r.stdout.strip():raise RuntimeError('unmanaged receiver/NPU process present: '+r.stdout)
  status('SILENCE_CAPTURE_RUNNING')
  silence=base+'/silence'
  remote(shlex.join([info['python'],'-I',info['root']+'/parameter_rx.py','--radio',info['radio'],
                    '--rx-uri',info['rx_uri'],'--out',silence,'--mode','manual','--gain','35','--seconds','10']),
                    log=HERE/'silence.log',timeout=60)
  pull(silence+'/restore_readback.json',HERE/'silence_restore.json')
  if json.loads((HERE/'silence_restore.json').read_text())['restore_verified'] is not True:raise RuntimeError('silence restore failed')
  status('SILENCE_CAPTURE_PASS')
  for label,gain in [('smoke35',35),('smoke25',25),('smokeAGC',None),('smoke45',45)]:
   scores[label]=experiment(info,base,label,gain,1)
  # Full frozen-set comparison follows only a healthy baseline, not a broken pipeline.
  if scores['smoke35']['correct']['8']<20:raise RuntimeError('baseline smoke <20/24; freeze evidence and diagnose before long RF')
  for label,gain in [('full35',35),('full25',25),('fullAGC',None),('full45',45)]:
   scores[label]=experiment(info,base,label,gain,10)
  write(HERE/'PARAMETER_RESULTS.json',dict(scores=scores,production_changed=False,
       independent_message_generalization_proven=False,second_session_revalidation_pending=True))
  status('PARAMETER_TESTS_COMPLETE',scores={k:v['correct'] for k,v in scores.items()})
 finally:
  # Stop only RX PIDs this run created, validating their cmdline and exact output path.
  for p in HERE.glob('*/rx_process.json'):
   proc=json.loads(p.read_text())
   code="import pathlib,os,signal; pid="+str(proc['pid'])+"; p=pathlib.Path('/proc')/str(pid)/'cmdline'; cmd=p.read_bytes().decode(errors='replace') if p.exists() else ''; expected="+repr(proc['out'])+";\nif 'parameter_rx.py' in cmd and expected in cmd: os.kill(pid,signal.SIGINT)\n"
   try:pyremote(code)
   except Exception as e:restore['capture_cleanup_error']=str(e)
  if stopped and info['receiver_was_active']:
   r=remote('systemctl start rml24-receiver.service; systemctl is-active rml24-receiver.service',check=False)
   restore.update(receiver_restart_rc=r.returncode,receiver_state=r.stdout.strip())
  write(HERE/'restore_services.json',restore)

if __name__=='__main__':
 HERE.mkdir(exist_ok=True)
 if '--inspect' in sys.argv:
  r=remote("cat /opt/rml24-system/startup/start-receiver.sh; sha256sum /opt/rml24-system/rml24_final/recovery/candidate_two_dc.py /root/amr_rescue_gmsk_candidate_20261026/candidate_two_dc.py; find /root -maxdepth 5 -type f -name '*bf16*' 2>/dev/null | head -n 30",check=False)
  print(r.stdout,r.stderr);sys.exit(r.returncode)
 lock=HERE/'execution.lock'
 if lock.exists():raise RuntimeError('existing execution lock; inspect process before restarting')
 lock.write_text(str(os.getpid()))
 try:main()
 except BaseException as e:
  status('FAILED_STOPPED_FOR_REVIEW',error=str(e));(HERE/'failure.log').write_text(traceback.format_exc(),encoding='utf8');raise
 finally:lock.unlink(missing_ok=True)
