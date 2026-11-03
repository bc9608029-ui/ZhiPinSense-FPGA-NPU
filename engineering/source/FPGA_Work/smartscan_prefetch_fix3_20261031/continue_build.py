from pathlib import Path
import json,time,subprocess,shutil,hashlib,traceback
r=Path('E:/FPGA_Work/smartscan_prefetch_fix3_20261031');viv='D:/Xilinx_2018_3/Vivado/2018.3/bin/vivado.bat'
def state(stage,**kw):
 (r/'BUILD_STATUS.json').write_text(json.dumps(dict(stage=stage,updated=time.time(),**kw),indent=2));print(stage,flush=True)
def call(script,log,limit):
 with (r/log).open('w') as f:
  q=subprocess.run([viv,'-mode','batch','-source',str(r/script),'-nolog','-nojournal'],cwd=r,stdout=f,stderr=subprocess.STDOUT,shell=True,timeout=limit)
 if q.returncode:raise RuntimeError(script+' failed; see '+log)
try:
 state('WAIT_PRIOR_BUILD_BEFORE_REPLACING_SOURCE')
 deadline=time.monotonic()+1800
 while 'FIX3_BRAM_FULL_SYNTH_PASS' not in (r/'build_fix3_bram.log').read_text(errors='replace'):
  if time.monotonic()>deadline:raise RuntimeError('Prior synthesis did not complete')
  time.sleep(5)
 shutil.copyfile(r/'fft_frame_prefetch.sv',r/'fpga/smartscan_integration/rtl/fft_frame_prefetch.sv')
 # Final module must match the tested single-read-port revision.
 s=(r/'fft_frame_prefetch.sv').read_text();assert 'mem[read_addr]' in s
 (r/'build_fix3_final.tcl').write_text((r/'build_fix3.tcl').read_text().replace('FIX3_FULL_SYNTH_PASS','FIX3_FINAL_SYNTH_PASS'))
 state('FINAL_SINGLE_BRAM_FULL_SYNTHESIS',prefetch_sha=hashlib.sha256((r/'fft_frame_prefetch.sv').read_bytes()).hexdigest())
 call('build_fix3_final.tcl','build_fix3_final.log',1800)
 assert 'FIX3_FINAL_SYNTH_PASS' in (r/'build_fix3_final.log').read_text(errors='replace')
 t=(r/'fpga/implement_fix2.tcl').read_text().replace('reports_fix2','reports_fix3').replace('routed_fix2.dcp','routed_fix3.dcp')
 t=t.replace('array set n {buffer 0 engine_in 0 engine_out 0 scan_in 0 fft_ram 0}','array set n {buffer 0 engine_in 0 engine_out 0 scan_in 0 fft_ram 0 prefetch 0}')
 t=t.replace('fft_ram {u_smart_scan/u_scan/u_fft/*}','fft_ram {u_smart_scan/u_scan/u_fft/*}\n        prefetch {u_smart_scan/u_scan/u_fft/u_prefetch/*}')
 t=t.replace('foreach key {buffer engine_in engine_out scan_in fft_ram}','foreach key {buffer engine_in engine_out scan_in fft_ram prefetch}')
 (r/'implement_fix3.tcl').write_text(t)
 state('FINAL_IMPLEMENTATION_AND_ROUTE')
 call('implement_fix3.tcl','implement_fix3.log',5400)
 assert (r/'reports_fix3/routed_fix3.dcp').exists()
 state('ROUTE_COMPLETE_PENDING_TIMING_REVIEW_NO_BITSTREAM',new_candidate_board_tested=False,original_board_restored=True)
except Exception:
 state('BUILD_STOPPED_WITH_EVIDENCE',error=traceback.format_exc());raise
