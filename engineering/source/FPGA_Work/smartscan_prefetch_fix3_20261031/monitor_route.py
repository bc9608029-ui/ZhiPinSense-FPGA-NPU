from pathlib import Path
import time,json
r=Path('E:/FPGA_Work/smartscan_prefetch_fix3_20261031');deadline=time.monotonic()+5400
while True:
 s=(r/'resume_implementation_fix3_checkpoint.log').read_text(errors='replace')
 value={'stage':'IMPLEMENTATION_ROUTE_RUNNING','updated':time.time(),'root_cause_proven':False,'new_candidate_board_tested':False,'board_original_restored':True}
 if 'FIX2_ROUTED_REPORTS_READY_NO_BITSTREAM' in s:
  value['stage']='ROUTE_COMPLETE_PENDING_TIMING_REVIEW_NO_BITSTREAM'
 elif '\nERROR:' in s:
  value['stage']='IMPLEMENTATION_STOPPED_INSPECT_LOG'
 elif time.monotonic()>deadline:value['stage']='MONITOR_TIMEOUT_INSPECT_PROCESSES'
 (r/'BUILD_STATUS.json').write_text(json.dumps(value,indent=2))
 if value['stage']!='IMPLEMENTATION_ROUTE_RUNNING':print(value['stage'],flush=True);break
 time.sleep(10)
