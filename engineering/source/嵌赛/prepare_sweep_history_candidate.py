"""Copy the software-only stable source baseline, without touching originals."""
from pathlib import Path
import shutil, json, hashlib

root=Path(__file__).parent/'rml24_sweep_history_20261029'
root.mkdir(exist_ok=False)
base=Path('F:/rml24_standalone_execution_20261027/candidate')
final=Path('F:/嵌赛/rml24_mainchain_finalize1_20261028/candidate/overlay')
for name in ['rml24_final','ui_sw','board_package','sdr_adapter']:
    shutil.copytree(base/name,root/'candidate'/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc','build*','*.o','*.elf'))
for p in final.rglob('*'):
    if p.is_file():
        dst=root/'candidate'/p.relative_to(final);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dst)
for name in ['tests','scripts','docs','evidence','previews','dist']:(root/name).mkdir()
files={str(p.relative_to(root/'candidate')).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'candidate').rglob('*') if p.is_file()}
(root/'evidence'/'BASELINE_IDENTITY.json').write_text(json.dumps({'base':str(base),'stable_overlay':str(final),'files':files},indent=2),encoding='utf-8')
print(root)
