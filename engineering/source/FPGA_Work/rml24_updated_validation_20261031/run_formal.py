from pathlib import Path
import json,hashlib,subprocess,sys
r=Path(__file__).parent
freeze=json.loads((r/'HELPERS_FREEZE.json').read_text())
for rel,sha in freeze.items():assert hashlib.sha256((r/rel).read_bytes()).hexdigest()==sha,rel
for file,digest in json.loads((r/'EXTERNAL_DEPENDENCIES.json').read_text()).items():assert hashlib.sha256(Path(file).read_bytes()).hexdigest()==digest,file
approval=json.loads((r/'APPROVAL.json').read_text());assert approval['helpers_sha256']==hashlib.sha256((r/'HELPERS_FREEZE.json').read_bytes()).hexdigest() and approval['allowed'] and approval['plan_sha256']==hashlib.sha256((r/'FORMAL_PLAN.json').read_bytes()).hexdigest()
for name in ('search240','sweep24'):
 d=r/name
 with (d/'continue_device.log').open('w') as f:subprocess.run([sys.executable,'-u',str(d/'continue_device.py')],stdout=f,stderr=subprocess.STDOUT,check=True)
 assert not (d/'FAILURE.json').exists(),'hardware/process failure; stop remaining tests'
 subprocess.run([sys.executable,str(r/'audit_formal.py'),name],check=True)
 # Keep all completed failures; no automatic re-test or deployment.
 print(name+' audited',flush=True)
print('ALL_ROUNDS_AUDITED_NOT_DEPLOYED',flush=True)
