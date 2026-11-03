from pathlib import Path
import json,time,subprocess,sys
r=Path(__file__).parent;deadline=time.monotonic()+900
while True:
 v=json.loads((r/'DEVICE_STATUS.json').read_text())
 if v['stage']=='DEVICE_PHASE_ENDED_ORIGINAL_RESTORED':break
 if (r/'FAILURE.json').exists():raise RuntimeError('RF functional run failed; preserve evidence')
 if time.monotonic()>deadline:raise RuntimeError('Wait timed out')
 time.sleep(5)
subprocess.run([sys.executable,str(r/'audit_gui_rf.py')],check=True)
