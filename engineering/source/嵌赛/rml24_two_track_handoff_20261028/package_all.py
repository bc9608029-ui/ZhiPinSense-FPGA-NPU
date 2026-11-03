#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,zipfile

BASE=Path(__file__).resolve().parents[1]
names=['rml24_mainchain_freeze_prep_20261028','rml24_fpga_smart_scan_prep_20261028']
art=[]
for name in names:
    src=BASE/name; out=BASE/(name+'.zip')
    files=[p for p in src.rglob('*') if p.is_file() and '__pycache__' not in p.parts and 'selftest_work' not in p.parts]
    sums=[]
    for p in sorted(files): sums.append(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(src).as_posix())
    (src/'SHA256SUMS.txt').write_text('\n'.join(sums)+'\n',encoding='utf-8')
    files=[p for p in src.rglob('*') if p.is_file() and '__pycache__' not in p.parts and 'selftest_work' not in p.parts]
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(files):
            info=zipfile.ZipInfo(p.relative_to(src).as_posix(),(2026,10,28,0,0,0)); info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644<<16; z.writestr(info,p.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    art.append({'file':out.name,'bytes':out.stat().st_size,'sha256':hashlib.sha256(out.read_bytes()).hexdigest()})
(Path(__file__).with_name('ARTIFACTS.json')).write_text(json.dumps({'status':'PC_PREP_COMPLETE_BOARD_WORK_PENDING','artifacts':art},indent=2)+'\n',encoding='utf-8')
print(json.dumps(art,indent=2))
