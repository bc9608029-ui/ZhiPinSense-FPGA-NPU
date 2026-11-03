"""Test user's manually loaded candidate. No programming, Flash or installs."""
import datetime,importlib.util,json,os,shlex,subprocess,sys,time,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('manual_helpers',ROOT/'run_tests.py');h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
spec=importlib.util.spec_from_file_location('canary_helpers',ROOT/'run_fpga_tests.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
OUT=ROOT/('fpga_manual_'+str(int(time.time())));OUT.mkdir();h.HERE=OUT
def status(stage,**v):
 h.write(OUT/'STATUS.json',dict(stage=stage,time=datetime.datetime.now().astimezone().isoformat(),pid=os.getpid(),**v))
 h.write(ROOT/'MANUAL_FPGA_CURRENT.json',dict(root=str(OUT),stage=stage,pid=os.getpid(),**v))
 print(stage,flush=True)
def main():
 info=json.loads((ROOT/'board_preflight.json').read_text())
 status('CONNECTING_MANUALLY_LOADED_CANDIDATE')
 fresh=json.loads(h.pyremote(h.PROBE,timeout=45).stdout.strip().splitlines()[-1])
 fresh['tx_uri']=info['tx_uri'];info=fresh;h.write(OUT/'board_preflight.json',info)
 driver_info=json.loads((ROOT/'fpga_execution/driver_source_identity.json').read_text());driver=driver_info['root']+'/scan_xrt'
 remote_base='/root/rml24_manual_fpga_'+str(int(time.time()));h.write(OUT/'remote_root.json',dict(root=remote_base))
 status('STOPPING_COMPETING_SERVICES')
 h.remote('systemctl stop rml24-receiver.service rml24-ui.service',log=OUT/'stop_services.log')
 other=h.remote('pgrep -ax npu_stream',check=False)
 if other.stdout.strip():raise RuntimeError('another NPU session remains active')
 status('FPGA_HARDWARE_PROBE_STARTED')
 h.remote(shlex.join([driver,'--probe']),log=OUT/'probe.log',timeout=45)
 status('FPGA_VERSION_IDLE_PASS_STARTING_SAME_IQ')
 h.remote('mkdir '+shlex.quote(remote_base))
 vectors=remote_base+'/vectors'
 h.remote(shlex.join([info['python'],'-I',info['root']+'/fpga/make_vectors.py','--out',vectors]))
 for backend in ['software','fpga','auto']:
  status('SAME_IQ_'+backend.upper())
  h.remote(shlex.join([info['python'],'-I',info['root']+'/fpga/run_suite.py','--vectors',vectors,
                      '--out',remote_base+'/'+backend,'--backend',backend,'--driver',driver]),
                      log=OUT/(backend+'.log'),timeout=1200)
  h.pull(remote_base+'/'+backend+'/summary.json',OUT/(backend+'_summary.json'))
 h.remote(shlex.join([info['python'],'-I',info['root']+'/fpga/same_iq.py','--iq',vectors+'/plus37.i16',
                     '--out',remote_base+'/fallback','--backend','auto','--driver','/nonexistent/rml24_intentional_missing_driver']),
                     log=OUT/'fallback.log')
 status('NPU_LIVENESS')
 h.pyremote(b.CANARY,[info['npu'],info['model'],remote_base+'/npu'],log=OUT/'npu_canary.log',timeout=120)
 status('RF_SMOKE24')
 h.experiment(info,remote_base,'candidate_smoke35',35,1)
 status('RF_REGRESSION240')
 h.experiment(info,remote_base,'candidate_full35',35,10)
 status('TESTS_COMPLETE_MANUAL_ORIGINAL_BIT_RESTORE_REQUIRED')
 h.write(OUT/'RESULT.json',dict(flash_written=False,automatic_programming=False,
       production_promoted=False,manual_rollback_required=True,formal_scan_backend_integrated=False))
if __name__=='__main__':
 try:main()
 except Exception as e:
  status('FAILED_SERVICES_LEFT_STOPPED_PENDING_REVIEW',error=str(e))
  (OUT/'failure.log').write_text(traceback.format_exc(),encoding='utf8');raise
