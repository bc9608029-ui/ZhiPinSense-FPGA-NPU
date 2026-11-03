from pathlib import Path
import hashlib,json
r=Path('/root/rml24_range_expansion_20261101/candidate');f=r/'candidate/rml24_final/board_runtime/standalone_receiver.py';i=r/'evidence/CANDIDATE_SOURCE_IDENTITY.json';d=json.loads(i.read_text());d[str(f.relative_to(r))]=hashlib.sha256(f.read_bytes()).hexdigest();i.write_text(json.dumps(d,indent=2));q=r/'PROMOTED_RELEASE.json';d=json.loads(q.read_text());d['files'][str(i.relative_to(r))]=hashlib.sha256(i.read_bytes()).hexdigest();q.write_text(json.dumps(d,indent=2));print('CANDIDATE_IDENTITIES_UPDATED')
