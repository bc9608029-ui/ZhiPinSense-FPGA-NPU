from pathlib import Path
import json,shutil,hashlib,subprocess
src=Path('/opt/rml24-integrated/current').resolve();dst=Path('/root/rml24_range_expansion_20261101/candidate');dst.parent.mkdir(exist_ok=True)
assert not dst.exists();shutil.copytree(src,dst)
f=dst/'candidate/rml24_final/board_runtime/standalone_receiver.py';s=f.read_text();assert 'default=2300000000' in s and 'default=2500000000' in s;s=s.replace('default=2300000000','default=70000000').replace('default=2500000000','default=6000000000');f.write_text(s)
r=json.loads((dst/'PROMOTED_RELEASE.json').read_text());r['files'][str(f.relative_to(dst))]=hashlib.sha256(f.read_bytes()).hexdigest();r['promotion_scope']='RANGE CANDIDATE ONLY; previous RF gate applies to original narrow profile';r['range_candidate_pending']=True;(dst/'PROMOTED_RELEASE.json').write_text(json.dumps(r,indent=2))
subprocess.run(['python3','-m','py_compile',str(f)],check=True)
print('ISOLATED_RANGE_CANDIDATE_READY',flush=True)
