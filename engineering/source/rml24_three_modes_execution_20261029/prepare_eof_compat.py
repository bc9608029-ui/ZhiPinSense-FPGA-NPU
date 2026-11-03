from pathlib import Path
import hashlib,json
r=Path('/root/rml24_three_modes_execution_20261029');p=r/'delivery/scripts/run_candidate.py';s=p.read_text();old="            if ui.poll() is not None or npu.poll() is not None:raise RuntimeError('UI/NPU exited unexpectedly')";assert s.count(old)==1
new="""            if ui.poll() is not None:raise RuntimeError('UI exited unexpectedly')
            if npu.poll() is not None:
                # Normal RX EOF can stop NPU just before RX writes final files.
                if npu.returncode != 0:raise RuntimeError('NPU failed rc='+str(npu.returncode))
                try:rx.wait(timeout=1.0)
                except subprocess.TimeoutExpired:raise RuntimeError('NPU exited while RX remained active')
                if rx.returncode != 0:raise RuntimeError('RX failed after NPU EOF')
                if 'NPU_STREAM_STOP' not in (run/'npu.log').read_text(errors='replace'):raise RuntimeError('Missing NPU stop accounting')
                result['normal_npu_eof_before_rx_reap']=True
                break"""
q=p.with_name('run_candidate_eof_compat.py');q.write_text(s.replace(old,new));(r/'SUPERVISOR_EOF_COMPAT.json').write_text(json.dumps(dict(original_sha=hashlib.sha256(p.read_bytes()).hexdigest(),compat_sha=hashlib.sha256(q.read_bytes()).hexdigest(),scope='Accept only NPU rc0 with RX rc0 within1s, UI alive and STOP accounting; original retained'),indent=2))
worker='''import subprocess,json
from pathlib import Path
r=Path('/root/rml24_three_modes_execution_20261029');py='/root/miniconda3/envs/torch_v2.0.1_aarch64/bin/python3'
active=[u for u in ['rml24-ui','rml24-receiver'] if subprocess.run(['systemctl','is-active','--quiet',u]).returncode==0]
common=[py,str(r/'delivery/scripts/run_candidate_eof_compat.py'),'--legacy-root','/root/amr_rescue_20261025','--model-dir','/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16','--npu-sha','cc88cb0bf5cde766937d011978314b7dafd1122d0f18e1cbda731ec2f7a440d8']
results=[]
subprocess.run(common+['--check'],check=True)
try:
 subprocess.run(['systemctl','stop','rml24-receiver','rml24-ui'],check=True)
 for mode,name in [('FIXED','quiet_fixed02'),('BAND_SCAN','quiet_lock02'),('CONTINUOUS_SCAN','quiet_sweep02')]:
  with (r/(name+'_driver.log')).open('w') as f:rc=subprocess.run(common+['--run',str(r/name),'--mode',mode,'--duration-sec','60','--history-file',str(r/'candidate_history.txt')],stdout=f,stderr=subprocess.STDOUT).returncode
  report=json.loads((r/name/'supervisor.json').read_text());results.append(dict(mode=mode,rc=rc,report=report));(r/'QUIET_RESULTS.json').write_text(json.dumps(results,indent=2))
  print(mode,rc,report,flush=True)
  if rc or not report['clean_stop']:raise RuntimeError('Short test failed')
finally:
 if subprocess.run(['pgrep','-x','npu_stream'],stdout=subprocess.DEVNULL).returncode==0:raise RuntimeError('NPU remains active; restoration withheld')
 for u in active:subprocess.run(['systemctl','start',u],check=True)
 print('ORIGINAL_SERVICES_RESTORED',active,flush=True)
'''
(r/'retry_quiet_modes.py').write_text(worker)
print('COMPAT_AND_RETRY_READY')
