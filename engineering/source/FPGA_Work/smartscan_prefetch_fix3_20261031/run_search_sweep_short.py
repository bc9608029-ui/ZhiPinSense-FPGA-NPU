from pathlib import Path
import subprocess,sys,json,time
r=Path(__file__).parent
for name in ['phase18_search_shared','phase19_sweep_shared']:
 p=r/name
 with (p/'continue_device.log').open('w') as f:q=subprocess.run([sys.executable,'-u',str(p/'continue_device.py')],stdout=f,stderr=subprocess.STDOUT)
 if q.returncode or (p/'FAILURE.json').exists():raise RuntimeError('Round blocked; preserve evidence '+name)
 state=json.loads((p/'DEVICE_STATUS.json').read_text());assert state['stage']=='DEVICE_PHASE_ENDED_ORIGINAL_RESTORED'
 print(name+' COMPLETE_PENDING_EVIDENCE_AUDIT',flush=True)
