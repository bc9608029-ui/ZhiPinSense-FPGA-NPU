import hashlib,json,tarfile
from pathlib import Path
r=Path(__file__).parent;out=r/'diag_fixed01_evidence.tar.gz'
info=json.loads((r/'archive_info.json').read_text())
if hashlib.sha256(out.read_bytes()).hexdigest()!=info['sha256']:raise RuntimeError('Archive SHA mismatch')
dest=r/'board';dest.mkdir(exist_ok=True)
with tarfile.open(out) as t:
    for m in t.getmembers():
        if not (m.isfile() or m.isdir()):raise RuntimeError('Non-regular archive member')
        try:(dest/m.name).resolve().relative_to(dest.resolve())
        except ValueError:raise RuntimeError('Archive traversal')
    t.extractall(dest)
base=dest/'diag_fixed01';hashes=json.loads((base/'evidence_SHA256.json').read_text())
for name,sha in hashes.items():
    if hashlib.sha256((base/name).read_bytes()).hexdigest()!=sha:raise RuntimeError('File SHA mismatch '+name)
print('EVIDENCE_EXTRACT_PASS files=%d sha256=%s'%(len(hashes),info['sha256']))
