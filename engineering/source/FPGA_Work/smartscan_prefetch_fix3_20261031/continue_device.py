from pathlib import Path
import subprocess,time,json,hashlib,re,traceback
r=Path('E:/FPGA_Work/smartscan_prefetch_fix3_20261031');tool='D:/Xilinx_2018_3/Vivado/2018.3/bin/vivado.bat';serial='E:/scan_exec_20261027/serial.ps1';rollback=Path('E:/FPGA_Work/rml24_boardtest_20261030/program_original_E.tcl')
def state(s,**kw):(r/'DEVICE_STATUS.json').write_text(json.dumps(dict(stage=s,time=time.time(),**kw),indent=2));print(s,flush=True)
def board(c):
 q=subprocess.run(['powershell','-NoProfile','-File',serial,'-Command',c,'-Seconds','3'],capture_output=True,timeout=30);s=q.stdout.decode(errors='replace');(r/'device_serial.log').open('a',encoding='utf-8').write(s+'\n');q.check_returncode();return s

def program(tcl,log):
 with (r/log).open('w') as f:q=subprocess.run([tool,'-mode','batch','-source',str(tcl),'-nolog','-nojournal'],cwd=r,stdout=f,stderr=subprocess.STDOUT,shell=True,timeout=240)
 q.check_returncode();assert 'PL_DDR_MANDATORY_CORE_PROGRAMMING_COMPLETE' in (r/log).read_text(errors='replace'),'configuration not verified'
programmed=False;states=[];remote='/root/rml24_fix3_'+str(int(time.time()))
try:
 state('WAIT_FOR_VERIFIED_CONVERTED_BIT')
 deadline=time.monotonic()+1800
 bit=r/'outputs/smartscan_fix3_candidate/smartscan_fix3_vendor_auto_disable_icap.bit'
 while True:
  s=(r/'generate_bit_fix3.log').read_text(errors='replace')
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
 # Predetermined eight rounds, stop immediately on first failing suite.
 cmd="mkdir "+remote+"; nohup bash -c 'for i in $(seq 1 8); do timeout 90 /root/miniconda3/envs/torch_v2.0.1_aarch64/bin/python3 -I /root/rml24_test_setup_w1QsCF/rml24_test_readiness_20261030/fpga/run_suite.py --vectors /root/rml24_manual_fpga_1793380256/vectors --out "+remote+"/repeat_$i --backend fpga --driver /root/rml24_fpga_diag_1793380588/scan_xrt; rc=$?; echo REPEAT=$i RC=$rc; if [ $rc -ne 0 ]; then break; fi; done; echo FIX3_MATRIX_DONE' > "+remote+"/matrix.log 2>&1 < /dev/null & echo MATRIX_STARTED"
 board(cmd);state('SAME_IQ_MATRIX_RUNNING',board_evidence=remote)
 deadline=time.monotonic()+1000
 while True:
  time.sleep(8);s=board('cat '+remote+'/matrix.log')
  if 'FIX3_MATRIX_DONE' in s.splitlines():break
  if time.monotonic()>deadline:raise RuntimeError('Matrix timeout; rollback required')
 passed=sum(1 for line in s.splitlines() if re.fullmatch(r'REPEAT=\d+ RC=0',line));state('MATRIX_FINISHED',passed_rounds=passed,planned_rounds=8,board_evidence=remote,accepted=False)
 if passed!=8:raise RuntimeError('Matrix fault reproduced; preserve evidence')
except Exception:state('TEST_FAILED_OR_BLOCKED',error=traceback.format_exc(),board_evidence=remote)
finally:
 if programmed:
  state('RESTORING_ORIGINAL_BIT');program(rollback,'device_rollback.log')
 if states:
  board('systemctl start '+' '.join(states)+'; systemctl is-active '+' '.join(states))
 state('DEVICE_PHASE_ENDED_ORIGINAL_RESTORED' if programmed else 'NO_NEW_BIT_LOADED',board_evidence=remote,production_promoted=False,rf_tested=False,npu_liveness_pending=programmed)
