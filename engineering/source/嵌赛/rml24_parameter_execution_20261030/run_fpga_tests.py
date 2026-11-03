"""Temporary JTAG candidate tests with unconditional original-bit rollback.
Called only after parameter baseline validation. Never writes Flash/BOOT.
"""
import datetime,hashlib,importlib.util,json,os,shlex,shutil,subprocess,sys,time,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parent
PREP=ROOT.parent/'rml24_test_readiness_20261030'
OUT=ROOT/'fpga_execution'
ASCII=Path('F:/FPGA_Work/rml24_boardtest_20261030')
VIVADO='D:/Xilinx2018.3/Vivado/2018.3/bin/vivado.bat'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name,value):
 OUT.mkdir(exist_ok=True);(OUT/name).write_text(json.dumps(value,indent=2),encoding='utf8')
def status(stage,**v):save('STATUS.json',dict(stage=stage,time=datetime.datetime.now().astimezone().isoformat(),**v));print(stage,flush=True)
def tool(script,log,timeout=180):
 env=dict(os.environ,TEMP=str(ASCII/'tmp'),TMP=str(ASCII/'tmp'),FMSH_PROCISE_PATH='D:/fudanwei/Procise')
 with (OUT/log).open('w',encoding='utf8') as f:
  p=subprocess.run([VIVADO,'-mode','batch','-source',str(script),'-nolog','-nojournal'],cwd=ASCII,
                   stdout=f,stderr=subprocess.STDOUT,timeout=timeout,env=env,shell=True)
 if p.returncode:raise RuntimeError('JTAG tool failed; inspect '+log)

CANARY=r'''
import subprocess,socket,time,struct,json,sys,os
from pathlib import Path
npu,model,folder=sys.argv[1:];folder=Path(folder);folder.mkdir()
log=(folder/'npu.log').open('w')
p=subprocess.Popen([npu,model+'/rml24_adamrv11_bf16.json',model+'/rml24_adamrv11_bf16.raw',str(folder/'npu.sock')],stdout=log,stderr=subprocess.STDOUT)
try:
 for i in range(200):
  if (folder/'npu.sock').exists():break
  assert p.poll() is None,'NPU exited';time.sleep(.1)
 with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as s:
  s.settimeout(30);s.connect(str(folder/'npu.sock'));answers=[]
  for i in range(8):
   s.sendall(bytes(8192));data=b''
   while len(data)<96:
    b=s.recv(96-len(data));assert b,'NPU EOF';data+=b
   values=struct.unpack('<24f',data)
   assert all(__import__('math').isfinite(v) for v in values),'nonfinite canary'
   answers.append(max(range(24),key=lambda k:values[k]))
 print(json.dumps(dict(kind='ZERO_INPUT_NPU_LIVENESS_ONLY',finite=8,total=8,pred=answers)))
finally:
 p.terminate()
 try:p.wait(timeout=15)
 except subprocess.TimeoutExpired:p.kill();p.wait();raise RuntimeError('NPU cleanup required hard kill')
 log.close()
'''

def main():
 spec=importlib.util.spec_from_file_location('rf_helpers',ROOT/'run_tests.py');h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
 OUT.mkdir(exist_ok=True);info=json.loads((ROOT/'board_preflight.json').read_text());h.HERE=OUT
 baseline=json.loads((ROOT/'smoke35/score.json').read_text())
 if not baseline.get('measurement_valid') or baseline['correct']['8']<20:raise RuntimeError('baseline gate forbids FPGA trial')
 status('BOARD_COMPILE')
 # Compile first: no configuration change while resolving compiler/SDK problems.
 driver_root='/root/rml24_fpga_driver_'+str(int(time.time()));h.remote('mkdir '+shlex.quote(driver_root))
 identities={}
 for name in ['scan_xrt.cpp','scan_protocol.hpp','test_protocol.cpp','build_board.sh']:
  src=PREP/'fpga'/name;h.push(src,driver_root+'/'+name);identities[name]=sha(src)
 save('driver_source_identity.json',dict(root=driver_root,files=identities,
      note='Job-local FRAME counter validated against frozen core_job_rst_n wiring; bitstream unchanged'))
 h.remote('bash '+shlex.quote(driver_root+'/build_board.sh'),log=OUT/'board_build.log',timeout=600)
 driver=driver_root+'/scan_xrt'
 ASCII.mkdir(parents=True,exist_ok=True);(ASCII/'tmp').mkdir(exist_ok=True)
 expected={'candidate.bit':('smartscan_fix2_disable_icap.bit','47b9e1fd2154104bb1bf34e247af07db6908f70436e2ec68845d617e47514ccd'),
           'original.bit':('rollback_original.bit','22fec95c64f3db727dd250e5768cdadec82f4c4d2de088392980b95a632932e9')}
 for target,(name,digest) in expected.items():
  src=PREP/'fpga'/name
  if sha(src)!=digest:raise RuntimeError('bit SHA mismatch '+name)
  shutil.copyfile(src,ASCII/target)
  if sha(ASCII/target)!=digest:raise RuntimeError('staged bit SHA mismatch '+target)
 source=Path('F:/FPGA_Work/pl_ddr_mandatory_core_v1/fpai_demo_fpga/program_pl_ddr_mandatory_core.tcl').read_text(encoding='utf8')
 lines=source.splitlines()
 if sum(line.startswith('set bit_file ') for line in lines)!=1:raise RuntimeError('unexpected historical JTAG script')
 for name in ['candidate','original']:
  text='\n'.join('set bit_file {'+(ASCII/(name+'.bit')).as_posix()+'}' if line.startswith('set bit_file ') else line for line in lines)+'\n'
  (ASCII/('program_'+name+'.tcl')).write_text(text,encoding='ascii')
 enum=Path('F:/FPGA_Work/pl_ddr_mandatory_core_v1/fpai_demo_fpga/enumerate_pl_jtag_v2.tcl')
 shutil.copyfile(enum,ASCII/'enumerate.tcl')
 status('JTAG_ENUMERATION_NO_PROGRAMMING')
 tool(ASCII/'enumerate.tcl','jtag_enumeration.log',180)
 states={}
 for service in ['rml24-receiver.service','rml24-ui.service']:
  states[service]=h.remote(shlex.join(['systemctl','show',service,'--property=ActiveState','--value'])).stdout.strip()
 save('original_service_states.json',states)
 h.remote('systemctl cat rml24-ui.service; cat /opt/rml24-system/startup/start-ui.sh; cat /etc/rc.local',
          log=OUT/'original_display_startup.log',check=False)
 programmed=False;restored=False;test_error=None;remote_base='/root/rml24_fpga_exec_'+str(int(time.time()))
 save('remote_root.json',dict(root=remote_base))
 h.remote('mkdir '+shlex.quote(remote_base))
 try:
  h.remote('systemctl stop rml24-receiver.service rml24-ui.service')
  # Fails closed on unexpected NPU holders; do not kill unrelated processes.
  active=h.remote('pgrep -ax npu_stream',check=False)
  if active.stdout.strip():raise RuntimeError('another NPU process still owns hardware')
  status('PROGRAMMING_TEMPORARY_CANDIDATE')
  programmed=True;tool(ASCII/'program_candidate.tcl','jtag_candidate.log',180)
  status('CANDIDATE_MMIO_AND_DDR_TESTS')
  h.remote(shlex.join([driver,'--probe']),log=OUT/'probe.log')
  vectors=remote_base+'/vectors'
  h.remote(shlex.join([info['python'],'-I',info['root']+'/fpga/make_vectors.py','--out',vectors]))
  for backend in ['software','fpga','auto']:
   h.remote(shlex.join([info['python'],'-I',info['root']+'/fpga/run_suite.py','--vectors',vectors,
                       '--out',remote_base+'/'+backend,'--backend',backend,'--driver',driver]),
                       log=OUT/(backend+'_suite.log'),timeout=1200)
   h.pull(remote_base+'/'+backend+'/summary.json',OUT/(backend+'_summary.json'))
  h.remote(shlex.join([info['python'],'-I',info['root']+'/fpga/same_iq.py','--iq',vectors+'/plus37.i16',
                      '--out',remote_base+'/launch_failure','--backend','auto','--driver','/nonexistent/rml24_intentional_missing_driver']),
                      log=OUT/'fallback.log')
  status('CANDIDATE_NPU_LIVENESS')
  h.pyremote(CANARY,[info['npu'],info['model'],remote_base+'/candidate_npu'],log=OUT/'candidate_npu.log',timeout=120)
  status('CANDIDATE_RF_SMOKE')
  h.experiment(info,remote_base,'candidate_smoke35',35,1)
  status('CANDIDATE_RF_FIXED_SET')
  h.experiment(info,remote_base,'candidate_full35',35,10)
  save('TEST_RESULT.json',dict(state='ISOLATED_FPGA_DIAGNOSTICS_AND_RF_REGRESSION_COMPLETE',
       production_receiver_scan_backend_integrated=False,flash_written=False,production_promoted=False,
       continuous_1000_frames_not_yet_tested=True))
 except Exception as exc:
  test_error=str(exc);save('FAILURE_RESULT.json',dict(error=test_error,traceback=traceback.format_exc()))
  raise
 finally:
  status('RESTORING_ORIGINAL_BITSTREAM')
  if programmed:
   # Stop only test RX PIDs with verified argv, before restoring the PL.
   for p in OUT.glob('*/rx_process.json'):
    record=json.loads(p.read_text());pid=record['pid'];path=record['out']
    code="import pathlib,os,signal; p=pathlib.Path('/proc')/"+repr(str(pid))+"/'cmdline'; s=p.read_bytes().decode(errors='replace') if p.exists() else '';\nif 'parameter_rx.py' in s and "+repr(path)+" in s: os.kill("+str(pid)+",signal.SIGINT)\n"
    h.pyremote(code)
   rollback_error=None
   for attempt in range(2):
    try:tool(ASCII/'program_original.tcl','jtag_rollback_'+str(attempt)+'.log',180);restored=True;break
    except Exception as e:rollback_error=e;time.sleep(3)
   if not restored:raise RuntimeError('original bitstream restore failed: '+str(rollback_error))
   h.pyremote(CANARY,[info['npu'],info['model'],remote_base+'/rollback_npu'],log=OUT/'rollback_npu.log',timeout=120)
  else:restored=True
  for service in ['rml24-ui.service','rml24-receiver.service']:
   if restored and states.get(service) in ('active','activating','reloading'):h.remote(shlex.join(['systemctl','start',service]))
  save('RESTORE_RESULT.json',dict(original_bit_restored=restored,services_requested=states,flash_written=False,test_error=test_error))
  h.remote('systemctl is-active rml24-ui.service rml24-receiver.service; journalctl -u rml24-ui.service -n 12 --no-pager',
           log=OUT/'restored_services.log',check=False)
  if test_error:status('FPGA_TRIAL_FAILED_ORIGINAL_RESTORED',error=test_error)
 status('FPGA_TESTS_FINISHED_ORIGINAL_RESTORED')

if __name__=='__main__':main()
