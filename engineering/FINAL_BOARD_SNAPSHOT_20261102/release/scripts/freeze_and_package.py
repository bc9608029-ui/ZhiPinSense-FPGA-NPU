"""Deterministic software-only delivery, no model weights or FPGA image."""
from pathlib import Path
import hashlib,json,zipfile,io

ROOT=Path(__file__).resolve().parents[1]
def digest(b):return hashlib.sha256(b).hexdigest()
def candidate_files():
    for p in sorted((ROOT/'candidate').rglob('*')):
        if not p.is_file() or '__pycache__' in p.parts or 'bin' in p.relative_to(ROOT).parts:continue
        if p.suffix.lower() in ['.pyc','.o','.elf','.exe']:continue
        rel=p.relative_to(ROOT).as_posix()
        # Only the canonical wrapper/entry and its one shared legacy helper are shipped.
        if '/rml24_final/board_runtime/' in rel and p.name not in {
            'standalone_receiver.py','receiver_repeat_mean_gapfix1.py','repeat_mean_candidate.py',
            'rml24_dualmode_receiver_centered_v2.py'}:continue
        if '/rml24_final/docs/' in rel or '/rml24_final/contract/' in rel or rel.endswith('rml24_final/README.md'):continue
        yield p

def freeze():
    files={p.relative_to(ROOT).as_posix():digest(p.read_bytes()) for p in candidate_files()}
    (ROOT/'evidence/CANDIDATE_SOURCE_IDENTITY.json').write_text(json.dumps(files,indent=2)+'\n',encoding='utf-8',newline='\n')
    before=json.loads((ROOT/'evidence/BASELINE_IDENTITY.json').read_text())['files']
    changes={rel:{'before':before.get(rel.removeprefix('candidate/')),'after':sha} for rel,sha in files.items()
             if before.get(rel.removeprefix('candidate/'))!=sha}
    (ROOT/'evidence/CHANGED_FILES.json').write_text(json.dumps(changes,indent=2)+'\n',encoding='utf-8',newline='\n')
    for rel in ['rml24_final/recovery/candidate_two_dc.py','rml24_final/runtime/receiver_core.py',
                'rml24_final/board_runtime/repeat_mean_candidate.py']:
        assert digest((ROOT/'candidate'/rel).read_bytes())==before[rel],rel
    print('FROZEN_PROTECTED_PASS two_dc receiver_core repeat_mean')

def package():
    selected=list(candidate_files())
    for name in ['docs','previews','tests','evidence']:
        selected.extend(p for p in (ROOT/name).rglob('*') if p.is_file() and '__pycache__' not in p.parts and
                        'bin' not in p.relative_to(ROOT).parts and p.suffix not in ['.ppm','.pyc'])
    selected.extend(ROOT/'scripts'/n for n in ['run_candidate.py','check_cpp.sh','make_gui_fixture.py','freeze_and_package.py','run_offline_checks.py'])
    selected.append(ROOT/'NEXT_AGENT_HANDOFF.md')
    content={p.relative_to(ROOT).as_posix():p.read_bytes() for p in selected}
    content['SHA256SUMS.txt']=''.join(digest(b)+'  '+name+'\n' for name,b in sorted(content.items())).encode()
    def build():
        mem=io.BytesIO()
        with zipfile.ZipFile(mem,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for name,b in sorted(content.items()):
                info=zipfile.ZipInfo(name,date_time=(2026,10,29,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
                info.external_attr=0o100644<<16;z.writestr(info,b)
        return mem.getvalue()
    a=build();assert a==build(),'non-deterministic archive'
    path=ROOT/'dist/rml24_three_modes_history_candidate_20261029.zip';path.write_bytes(a)
    with zipfile.ZipFile(io.BytesIO(a)) as z:
        assert z.testzip() is None
        for line in z.read('SHA256SUMS.txt').decode().splitlines():
            sha,name=line.split('  ',1);assert digest(z.read(name))==sha,name
    (path.with_suffix('.zip.sha256')).write_text(digest(a)+'  '+path.name+'\n',encoding='ascii')
    print('PACKAGE_PASS files=%d bytes=%d sha256=%s'%(len(content)-1,len(a),digest(a)))

if __name__=='__main__':
    import sys
    freeze()
    if '--freeze-only' not in sys.argv:package()
