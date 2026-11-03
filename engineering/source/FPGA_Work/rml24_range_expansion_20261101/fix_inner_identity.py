from pathlib import Path
import json,hashlib,subprocess
r=Path('/root/rml24_range_expansion_20261101/candidate');b=r/'candidate/rml24_final';f=b/'board_runtime/standalone_receiver.py';w=b/'board_runtime/receiver_repeat_mean_gapfix1.py';old='ffdb47bff6834ca0a6ce267773dc731ebe439d8ce61d3595dbcf381f95be1801';new=hashlib.sha256(f.read_bytes()).hexdigest();s=w.read_text();assert old in s;s=s.replace(old,new);w.write_text(s)
i=r/'evidence/CANDIDATE_SOURCE_IDENTITY.json';d=json.loads(i.read_text());d[str(w.relative_to(r))]=hashlib.sha256(w.read_bytes()).hexdigest();i.write_text(json.dumps(d,indent=2));q=r/'PROMOTED_RELEASE.json';d=json.loads(q.read_text());d['files'][str(w.relative_to(r))]=hashlib.sha256(w.read_bytes()).hexdigest();d['files'][str(i.relative_to(r))]=hashlib.sha256(i.read_bytes()).hexdigest();q.write_text(json.dumps(d,indent=2))
subprocess.run(['/root/miniconda3/envs/torch_v2.0.1_aarch64/bin/python3','-c',"import sys;sys.path.insert(0,"+repr(str(w.parent))+");import receiver_repeat_mean_gapfix1 as m;m.verify_base();print('INNER_PREFLIGHT_PASS')"],check=True)
print('ALL_CANDIDATE_IDENTITIES_SYNCED',flush=True)
