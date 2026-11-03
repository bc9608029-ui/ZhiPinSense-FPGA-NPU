from pathlib import Path
import subprocess,time,json,hashlib,re,traceback
r=Path('E:/FPGA_Work/smartscan_prefetch_fix3_20261031/phase3');tool='D:/Xilinx_2018_3/Vivado/2018.3/bin/vivado.bat';serial='E:/scan_exec_20261027/serial.ps1';rollback=Path('E:/FPGA_Work/rml24_boardtest_20261030/program_original_E.tcl')
def state(s,**kw):(r/'DEVICE_STATUS.json').write_text(json.dumps(dict(stage=s,time=time.time(),**kw),indent=2));print(s,flush=True)
def board(c):
 q=subprocess.run(['powershell','-NoProfile','-File',serial,'-Command',c,'-Seconds','3'],capture_output=True,timeout=30);s=q.stdout.decode(errors='replace');(r/'device_serial.log').open('a',encoding='utf-8').write(s+'\n');q.check_returncode();return s

def program(tcl,log):
 with (r/log).open('w') as f:q=subprocess.run([tool,'-mode','batch','-source',str(tcl),'-nolog','-nojournal'],cwd=r,stdout=f,stderr=subprocess.STDOUT,shell=True,timeout=240)
 q.check_returncode();assert 'PL_DDR_MANDATORY_CORE_PROGRAMMING_COMPLETE' in (r/log).read_text(errors='replace'),'configuration not verified'
programmed=False;states=[];remote='/root/rml24_fix3_'+str(int(time.time()))
try:
 state('WAIT_PHASE2_ORIGINAL_RESTORED')
 deadline=time.monotonic()+1800
 while True:
  try:v=json.loads((r.parent/'phase2/DEVICE_STATUS.json').read_text())
  except (FileNotFoundError,json.JSONDecodeError):v={}
  if v.get('stage')=='DEVICE_PHASE_ENDED_ORIGINAL_RESTORED':break
  if v.get('stage')=='NO_NEW_BIT_LOADED' or time.monotonic()>deadline:raise RuntimeError('Phase2 did not complete')
  time.sleep(5)
 assert 'REPEAT=16 RC=0' in (r.parent/'phase2/device_serial.log').read_text(errors='replace'),'Phase2 full matrix not passed'
 state('WAIT_FOR_VERIFIED_CONVERTED_BIT')
 deadline=time.monotonic()+1800
 bit=r.parent/'outputs/smartscan_fix3_candidate/smartscan_fix3_vendor_auto_disable_icap.bit'
 while True:
  s=(r.parent/'generate_bit_fix3.log').read_text(errors='replace')
  if 'FIX3_VENDOR_BITGEN_FINISHED_WITH_INHERITED_NPU_EXCEPTION' in s and bit.exists():break
  if '\nERROR:' in s or time.monotonic()>deadline:raise RuntimeError('bit generation failed or timed out')
  time.sleep(5)
 assert bit.stat().st_size>1000000
 digest=hashlib.sha256(bit.read_bytes()).hexdigest();(r/'NEW_BIT_IDENTITY.json').write_text(json.dumps(dict(file=str(bit),sha256=digest,temporary_only=True),indent=2))
 template=Path('E:/FPGA_Work/rml24_boardtest_20261030/program_candidate_E.tcl').read_text();old='set bit_file {E:/FPGA_Work/rml24_boardtest_20261030/candidate.bit}';assert old in template
 (r/'program_fix3.tcl').write_text(template.replace(old,'set bit_file {'+bit.as_posix()+'}'))
 s=board('for u in rml24-ui rml24-receiver; do echo UNIT=$u; systemctl is-active $u; done')
 for u in ['rml24-ui','rml24-receiver']:
  if re.search(r'UNIT='+u+r'\r?\n(?:active|activating)\r?\n',s):states.append(u)
 assert len(states)==2,'Unexpected original services; do not reconfigure'
 s=board('systemctl stop rml24-receiver rml24-ui; if pgrep -x npu_stream >/dev/null; then echo NPU_OCCUPIED; else echo PL_USERS_STOPPED; fi')
 assert 'PL_USERS_STOPPED' in s.splitlines() and 'NPU_OCCUPIED' not in s.splitlines()
 state('TEMPORARY_PROGRAMMING',bit_sha=digest);programmed=True;program(r/'program_fix3.tcl','device_program.log')
 s=board('timeout 20 /root/rml24_fpga_diag_1793380588/scan_xrt --probe; echo PROBE_END')
 assert 'SMARTSCAN_PROBE version=1 idle=1' in s and 'error=0' in s,'Probe failed'

 state('VERIFY_PHASE2_BACKENDS')
 code="import json;from pathlib import Path;p=Path('/root/rml24_fix3_1793424787');a=json.loads((p/'auto/summary.json').read_text());b=json.loads((p/'fallback/result.json').read_text());assert a['passed']==8 and all(x['result']['backend_used']=='fpga' for x in a['results']);assert b['ok'] and b['backend_used']=='software' and 'driver_launch_failed' in b['fallback_reason'];print('AUTO_AND_FALLBACK_VERIFIED')"
 import base64
 def py(c):return 'python3 -c "import base64;exec(base64.b64decode(\''+base64.b64encode(c.encode()).decode()+'\'))"'
 out=board(py(code));assert 'AUTO_AND_FALLBACK_VERIFIED' in out.splitlines()
 state('CANDIDATE_NPU_LIVENESS')
 canary=Path(__file__).with_name('canary_code.txt').read_text()
 wrapper="import sys;sys.argv=['canary','/root/amr_rescue_20261025/build/npu_stream','/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16',"+repr(remote+'/candidate_npu')+"];\n"+canary+"\nprint('NPU_CANARY_DONE',flush=True)"
 board('mkdir '+remote+'; nohup /root/miniconda3/envs/torch_v2.0.1_aarch64/bin/python3 -c "import base64;exec(base64.b64decode(\''+base64.b64encode(wrapper.encode()).decode()+'\'))" > '+remote+'/canary.log 2>&1 < /dev/null & echo CANARY_STARTED')
 deadline=time.monotonic()+120
 while True:
  time.sleep(5);out=board('cat '+remote+'/canary.log')
  if 'NPU_CANARY_DONE' in out.splitlines():break
  if time.monotonic()>deadline:raise RuntimeError('NPU canary incomplete; inspect preserved log')
 assert '"finite": 8' in out,'NPU finite output missing'
 (r/'CANDIDATE_NPU_RECEIPT.json').write_text(json.dumps(dict(finite=8,total=8,kind='ZERO_INPUT_LIVENESS_ONLY_NOT_ACCURACY',board_evidence=remote)))

except Exception:
 (r/'FAILURE.json').write_text(json.dumps(dict(error=traceback.format_exc(),board_evidence=remote)));state('TEST_FAILED_OR_BLOCKED',error=traceback.format_exc(),board_evidence=remote)
finally:
 if programmed:
  state('RESTORING_ORIGINAL_BIT');program(rollback,'device_rollback.log')
 if states:
  board('systemctl start '+' '.join(states)+'; systemctl is-active '+' '.join(states))
 state('DEVICE_PHASE_ENDED_ORIGINAL_RESTORED' if programmed else 'NO_NEW_BIT_LOADED',board_evidence=remote,production_promoted=False,rf_tested=False,npu_liveness_pending=programmed)
