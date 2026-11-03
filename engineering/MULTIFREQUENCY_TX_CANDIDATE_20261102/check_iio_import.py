from pathlib import Path
import sys,subprocess,os,json
root=Path(__file__).resolve().parent/'pc_console';sys.path.insert(0,str(root))
from iio_runtime import environment,REQUIRED
rows=[]
for executable in ['D:/radioconda/python.exe','D:/Anaconda/python.exe']:
 updates=environment(executable,True);env=os.environ.copy();env.update(updates)
 code='import sys;sys.path.insert(0,'+repr(str(root))+');from tx_core import load_module,ROOT;m=load_module("probe_import_only",ROOT/"vendor/pluto_link_probe.py");print("DRIVER_IMPORT_OK_NO_CONTEXT_CREATED")'
 p=subprocess.run([executable,'-c',code],env=env,capture_output=True)
 print(executable,updates['LIBIIO_LIBRARY'],p.returncode,p.stdout.decode(errors='replace'),p.stderr.decode(errors='replace'))
 assert p.returncode==0
 rows.append(dict(executable=executable,library=updates['LIBIIO_LIBRARY'],required_exports=len(REQUIRED),returncode=p.returncode,device_context_created=False))
(root.parent/'IIO_IMPORT_CHECK.json').write_text(json.dumps(rows,indent=2),encoding='utf8')
