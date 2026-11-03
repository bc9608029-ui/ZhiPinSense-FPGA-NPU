from pathlib import Path
import hashlib,json,zipfile,tarfile
r=Path(r'E:\rml24_ac_execution_20261029')
with tarfile.open(str(r/'board_evidence.tar.gz')) as t:
 members=t.getmembers();assert all(m.isfile() for m in members);print('BOARD_EVIDENCE_FILES',len(members))
files=[p for p in r.rglob('*') if p.is_file() and p.name!='SHA256SUMS.json']
manifest={p.relative_to(r).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
(r/'SHA256SUMS.json').write_text(json.dumps(manifest,indent=2))
zpath=r.parent/'rml24_ac_test_handoff_20261029.zip'
with zipfile.ZipFile(str(zpath),'w',zipfile.ZIP_DEFLATED) as z:
 for p in files+[r/'SHA256SUMS.json']:z.write(str(p),p.relative_to(r).as_posix())
with zipfile.ZipFile(str(zpath)) as z:
 assert z.testzip() is None
 for n,h in manifest.items():assert hashlib.sha256(z.read(n)).hexdigest()==h
h=hashlib.sha256(zpath.read_bytes()).hexdigest();Path(str(zpath)+'.sha256').write_text(h+'  '+zpath.name+'\n');print(json.dumps(dict(zip=str(zpath),sha256=h,bytes=zpath.stat().st_size,content_files=len(manifest)),indent=2))
