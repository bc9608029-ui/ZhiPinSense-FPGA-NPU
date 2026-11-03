import tarfile,io,base64
from pathlib import Path
r=Path('/root/rml24_ac_execution_20261029');buf=io.BytesIO()
with tarfile.open(fileobj=buf,mode='w:gz') as t:
 for name in ['short_fixed01','short_fixed02','ui_scan01','launch_scripts']:
  for p in (r/name).rglob('*'):
   if p.is_file() and not p.is_symlink():t.add(str(p),arcname=p.relative_to(r).as_posix(),recursive=False)
 for p in r.glob('*.json'):t.add(str(p),arcname=p.name)
 for p in r.glob('*.log'):t.add(str(p),arcname=p.name)
 for rel in ['board_package/frequency_control.hpp','board_package/target_list_rml24_parse.hpp','ui_sw/ui_render.cpp','rml24_final/runtime/multisignal_scan_adapter.py']:
  p=r/'candidate'/rel;t.add(str(p),arcname='patched_candidate/'+rel)
print('EVIDENCE_BEGIN');print(base64.b64encode(buf.getvalue()).decode());print('EVIDENCE_END')
