from pathlib import Path
import subprocess,sys
base=Path(__file__).parent
for name in ['phase23_gui_newmessage1','phase24_gui_newmessage2']:
 r=base/name
 with (r/'continue_device.log').open('w') as f:subprocess.run([sys.executable,'-u',str(r/'continue_device.py')],stdout=f,stderr=subprocess.STDOUT,check=True)
 if (r/'FAILURE.json').exists():raise RuntimeError(name+' failed; stop further RF')
 with (r/'audit.log').open('w') as f:subprocess.run([sys.executable,'-u',str(r/'audit_gui_rf.py')],stdout=f,stderr=subprocess.STDOUT,check=True)
 print(name+' completed and audited',flush=True)
