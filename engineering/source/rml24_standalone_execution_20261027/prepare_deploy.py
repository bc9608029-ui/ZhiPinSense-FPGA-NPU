from pathlib import Path
import hashlib,tarfile,json
r=Path(__file__).parent;c=r/'candidate'
old={}
with tarfile.open(r.parent/'scan_exec_20261027/candidate_v2_fourpage_waterfall_tree.tar.gz') as t:
    for m in t.getmembers():
        if m.isfile():old['/'.join(m.name.split('/')[1:])]=hashlib.sha256(t.extractfile(m).read()).hexdigest()
changed=[]
with tarfile.open(r/'standalone_delta_final.tar.gz','w:gz') as t:
    for p in sorted(c.rglob('*')):
        if not p.is_file() or '__pycache__' in p.parts:continue
        rel=p.relative_to(c).as_posix()
        if rel.startswith(('board_package/','ui_sw/','sdr_adapter/')) and p.suffix not in ['.cpp','.hpp','.h','.sh']:continue
        if not rel.startswith(('board_package/','ui_sw/','sdr_adapter/','rml24_final/')):continue
        sha=hashlib.sha256(p.read_bytes()).hexdigest()
        if old.get(rel)!=sha:
            t.add(p,arcname=rel);changed.append(dict(file=rel,sha256=sha))
(r/'deployment_manifest.json').write_text(json.dumps(changed,indent=2))
print('CHANGED',len(changed),'BYTES',(r/'standalone_delta_final.tar.gz').stat().st_size)
for item in changed:print(item['file'])
