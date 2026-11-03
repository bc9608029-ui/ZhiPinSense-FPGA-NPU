from pathlib import Path
import subprocess,time,json,hashlib,re,traceback,sys,base64
r=Path('E:/FPGA_Work/rml24_sweep_timing_retry_20261031/sweep24');tool='D:/Xilinx_2018_3/Vivado/2018.3/bin/vivado.bat';serial='E:/scan_exec_20261027/serial.ps1';rollback=Path('E:/FPGA_Work/rml24_boardtest_20261030/program_original_E.tcl')
approval=json.loads((r.parent/'APPROVAL.json').read_text());assert approval['allowed'] and approval['plan_sha256']==hashlib.sha256((r.parent/'FORMAL_PLAN.json').read_bytes()).hexdigest()

def state(s,**kw):(r/'DEVICE_STATUS.json').write_text(json.dumps(dict(stage=s,time=time.time(),**kw),indent=2));print(s,flush=True)
def board(c):
 deadline=time.monotonic()+900
 while not (Path('E:/FPGA_Work/smartscan_prefetch_fix3_20261031')/'phase24_gui_newmessage2/GUI_24_RF_RESULT.json').exists():
  if time.monotonic()>deadline:raise RuntimeError('Prior GUI RF audit did not complete')
  time.sleep(5)
 prior=json.loads((Path('E:/FPGA_Work/smartscan_prefetch_fix3_20261031')/'phase24_gui_newmessage2/GUI_24_RF_RESULT.json').read_text());assert prior['gui_start_stop_and_restore_pass']
 q=subprocess.run(['powershell','-NoProfile','-File',serial,'-Command',c,'-Seconds','3'],capture_output=True,timeout=30);s=q.stdout.decode(errors='replace');(r/'device_serial.log').open('a',encoding='utf-8').write(s+'\n');q.check_returncode();return re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',s)

def program(tcl,log):
 with (r/log).open('w') as f:q=subprocess.run([tool,'-mode','batch','-source',str(tcl),'-nolog','-nojournal'],cwd=r,stdout=f,stderr=subprocess.STDOUT,shell=True,timeout=240)
 q.check_returncode();assert 'PL_DDR_MANDATORY_CORE_PROGRAMMING_COMPLETE' in (r/log).read_text(errors='replace'),'configuration not verified'
programmed=False;states=[];remote='/root/rml24_fix3_'+str(int(time.time()))
try:
 q=subprocess.run(['powershell','-NoProfile','-File','E:/FPGA_Work/rml24_timing_fix_20261031/clock_sync_monotonic.ps1'],capture_output=True,check=True)
 clock=json.loads(q.stdout.decode());assert clock['uncertainty_ns']<=250000000;(r/'clock_pre.json').write_text(json.dumps(clock,indent=2))
 state('WAIT_FOR_VERIFIED_CONVERTED_BIT')
 deadline=time.monotonic()+1800
 bit=Path('E:/FPGA_Work/smartscan_prefetch_fix3_20261031')/'outputs/smartscan_fix3_candidate/smartscan_fix3_vendor_auto_disable_icap.bit'
 while True:
  s=(Path('E:/FPGA_Work/smartscan_prefetch_fix3_20261031')/'generate_bit_fix3.log').read_text(errors='replace')
  if 'FIX3_VENDOR_BITGEN_FINISHED_WITH_INHERITED_NPU_EXCEPTION' in s and bit.exists():break
  if '\nERROR:' in s or time.monotonic()>deadline:raise RuntimeError('bit generation failed or timed out')
  time.sleep(5)
 assert bit.stat().st_size>1000000
 digest=hashlib.sha256(bit.read_bytes()).hexdigest();assert digest=='f42dd12f03bf81c65978b7034b45808efd5035f6a358cc54710f2404530a057c';(r/'NEW_BIT_IDENTITY.json').write_text(json.dumps(dict(file=str(bit),sha256=digest,temporary_only=True),indent=2))
 template=Path('E:/FPGA_Work/rml24_boardtest_20261030/program_candidate_E.tcl').read_text();old='set bit_file {E:/FPGA_Work/rml24_boardtest_20261030/candidate.bit}';assert old in template
 (r/'program_fix3.tcl').write_text(template.replace(old,'set bit_file {'+bit.as_posix()+'}'))
 s=board('for u in rml24-ui rml24-receiver; do echo UNIT=$u; systemctl is-active $u; done')
 for u in ['rml24-ui','rml24-receiver']:
  if re.search(r'UNIT='+u+r'\r?\n(?:active|activating)\r?\n',s):states.append(u)
 assert len(states)==2,'Unexpected original services; do not reconfigure'
 s=board('systemctl stop rml24-receiver rml24-ui; if (pgrep -x npu_stream >/dev/null || pgrep -f ^/root/rml24_fpga_shared_owner_20261031/build/npu_stream_shared >/dev/null); then echo NPU_OCCUPIED; else echo PL_USERS_STOPPED; fi')
 assert 'PL_USERS_STOPPED' in s.splitlines() and 'NPU_OCCUPIED' not in s.splitlines()
 state('TEMPORARY_PROGRAMMING',bit_sha=digest);programmed=True;program(r/'program_fix3.tcl','device_program.log')
 s=board('timeout 20 /root/rml24_fpga_diag_1793380588/scan_xrt --probe; echo PROBE_END')
 assert 'SMARTSCAN_PROBE version=1 idle=1' in s and 'error=0' in s,'Probe failed'

 import base64
 state('REAL_IQ_FIXED_MATRIX_RUNNING',board_evidence=remote)
 code="import sys;sys.argv=['real_iq',"+repr(remote)+"];\n"+(r/'real_iq_code.txt').read_text()
 b=base64.b64encode(code.encode()).decode()
 board('nohup /root/miniconda3/envs/torch_v2.0.1_aarch64/bin/python3 -c "import base64;exec(base64.b64decode(\''+b+'\'))" > '+remote+'.log 2>&1 < /dev/null & echo REAL_IQ_STARTED')

 state('WAIT_RX_READY_BEFORE_TX')
 ready=False
 for _ in range(15):
  out=board('test -f '+remote+'/quiet/rx.log && grep --color=never -a "^STANDALONE_READY" '+remote+'/quiet/rx.log')
  if any(x.startswith('STANDALONE_READY no_tcp=1') for x in out.splitlines()):ready=True;break
  time.sleep(1)
 assert ready,'RX not ready; do not transmit'
 txlog=(r/'tx.log').open('w');txprocess=subprocess.Popen([sys.executable,'-u','E:\\FPGA_Work\\rml24_sweep_timing_retry_20261031\\tx_formal.py','sweep24'],stdout=txlog,stderr=subprocess.STDOUT)
 state('SINGLE_RF_AND_UI_RUNNING',board_evidence=remote)
 deadline=time.monotonic()+1300
 while True:
  if txprocess.poll() not in (None,0):raise RuntimeError('TX failed; stop round')
  time.sleep(5);out=board('tail -2 '+remote+'.log')
  if 'REAL_IQ_MATRIX_DONE' in out.splitlines():break
  if any(x in out for x in ('Traceback','AssertionError','RuntimeError')):raise RuntimeError('Board run failed')
  if time.monotonic()>deadline:raise RuntimeError('Real IQ matrix incomplete')
 assert txprocess.wait(timeout=120)==0,'TX failed';txlog.close();restored=json.loads((r.parent/(r.name+'_tx')/'restore.json').read_text());assert restored['errors']==[] and all(x['ok'] for x in restored['readback']);state('REAL_IQ_MATRIX_DONE',board_evidence=remote)

except Exception:
 (r.parent/'STOP.request').write_text('Stop after control/device failure')
 (r/'FAILURE.json').write_text(json.dumps(dict(error=traceback.format_exc(),board_evidence=remote)));state('TEST_FAILED_OR_BLOCKED',error=traceback.format_exc(),board_evidence=remote)
finally:
 if 'txprocess' in globals() and txprocess.poll() is None:
  txprocess.wait(timeout=120)
 if programmed:
  # Gracefully stop only this run's recorded RX, then wait until its supervisor
  # has reaped RX/NPU/UI before reconfiguring PL. Never overlap old services.
  cleanup="import json,os,signal;from pathlib import Path;p=Path("+repr(remote+'/quiet/children.json')+");\nif p.exists():\n for v in json.loads(p.read_text()):\n  if v['role']=='rx':\n   q=Path('/proc')/str(v['pid'])/'cmdline';a=q.read_bytes().decode().rstrip('\\0').split('\\0') if q.exists() else []\n   if a==list(map(str,v['argv'])):os.kill(v['pid'],signal.SIGTERM)"
  cb=base64.b64encode(cleanup.encode()).decode();board('python3 -c "import base64;exec(base64.b64decode(\''+cb+'\'))"')
  safe=False
  for _ in range(18):
   out=board('if (pgrep -x npu_stream >/dev/null || pgrep -f ^/root/rml24_fpga_shared_owner_20261031/build/npu_stream_shared >/dev/null); then echo NPU_STILL_ACTIVE; else echo NPU_RELEASED; fi')
   if 'NPU_RELEASED' in out.splitlines():safe=True;break
   time.sleep(2)
  if not safe:raise RuntimeError('NPU still active; PL rollback and service restart withheld')
  state('RESTORING_ORIGINAL_BIT');program(rollback,'device_rollback.log')
 if states:
  board('systemctl start '+' '.join(states)+'; systemctl is-active '+' '.join(states))
 q=subprocess.run(['powershell','-NoProfile','-File','E:/FPGA_Work/rml24_timing_fix_20261031/clock_sync_monotonic.ps1'],capture_output=True,check=True);(r/'clock_post.json').write_text(q.stdout.decode())
 state('DEVICE_PHASE_ENDED_ORIGINAL_RESTORED' if programmed else 'NO_NEW_BIT_LOADED',board_evidence=remote,production_promoted=False,rf_tested=False,npu_liveness_pending=programmed)
