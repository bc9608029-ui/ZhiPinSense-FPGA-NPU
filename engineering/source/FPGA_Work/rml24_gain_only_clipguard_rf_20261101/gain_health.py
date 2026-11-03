from pathlib import Path
import subprocess,json
def healthy():
 try:
  pid=int(subprocess.check_output(['systemctl','show','rml24-integrated','-p','MainPID','--value']).strip());args=Path('/proc/%d/cmdline'%pid).read_bytes().decode().strip('\0').split('\0');run=Path(args[args.index('--run')+1]);children=json.loads((run/'children.json').read_text());alive=all(Path('/proc/%d/cmdline'%x['pid']).exists() for x in children if x['role'] in ('npu','ui','rx'));ready=alive and all(token in (run/(role+'.log')).read_text(errors='replace') for role,token in [('npu','NPU_STREAM_READY'),('ui','UI_FB_READY'),('rx','STANDALONE_READY')]);return dict(ready=ready,run=str(run))
 except Exception:return dict(ready=False)
print("GAIN_HEALTH "+json.dumps(healthy()))
