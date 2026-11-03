import hashlib,json,tarfile
from pathlib import Path
r=Path('/root/rml24_mainchain_diagnostic_20261028')
run=r/'diag_fixed01'
if not (run/'capture/final.json').exists():raise RuntimeError('RX is not finished')
final=json.loads((run/'capture/final.json').read_text())
traces=list((run/'evidence').glob('*.trace.json'))
if len(traces)!=final['records']:raise RuntimeError('Trace count differs from captured attempts')
files=[p for p in run.rglob('*') if p.is_file() and p.suffix!='.sock' and p.name!='evidence_SHA256.json']
hashes={}
for p in files:hashes[p.relative_to(run).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
(run/'evidence_SHA256.json').write_text(json.dumps(hashes,indent=2))
out=r/'diag_fixed01_evidence.tar.gz'
with tarfile.open(out,'w:gz',compresslevel=1) as t:t.add(run,arcname='diag_fixed01')
print(json.dumps(dict(archive=str(out),bytes=out.stat().st_size,
                     sha256=hashlib.sha256(out.read_bytes()).hexdigest(),traces=len(traces),final=final)),flush=True)
