from pathlib import Path
import json,shutil

def prune_completed(log_root,keep=1,proc_root=Path('/proc')):
 """Delete only old, cleanly completed owned runs; preserve faults/unknown/live."""
 log_root=Path(log_root).resolve();eligible=[]
 for p in log_root.iterdir():
  if p.is_symlink() or not p.is_dir() or p.resolve().parent!=log_root or not p.name.startswith('r'):continue
  try:
   receipt=json.loads((p/'supervisor.json').read_text());children=json.loads((p/'children.json').read_text())
   if receipt.get('clean_stop') is not True or receipt.get('hardware_reset_required') or receipt.get('error'):continue
   live=False
   for child in children:
    cmd=Path(proc_root)/str(int(child['pid']))/'cmdline'
    if cmd.exists() and cmd.read_bytes().decode().rstrip('\0').split('\0')==list(map(str,child['argv'])):live=True
   if not live:eligible.append(p)
  except (OSError,ValueError,KeyError,TypeError):continue
 eligible.sort(key=lambda p:p.stat().st_mtime_ns,reverse=True);removed=[]
 for p in eligible[keep:]:
  if p.resolve().parent!=log_root or p.is_symlink():raise RuntimeError('unsafe log path')
  shutil.rmtree(p);removed.append(p.name)
 return removed
