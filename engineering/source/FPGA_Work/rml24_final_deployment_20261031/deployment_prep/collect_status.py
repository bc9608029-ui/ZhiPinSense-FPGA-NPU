from pathlib import Path
import json,subprocess,os

def collect_status(release_root):
 root=Path(release_root).resolve();boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip();receipt=json.loads((root/'PROMOTED_RELEASE.json').read_text());runs=Path('/var/log/rml24-integrated');directories=[p for p in runs.glob('r*') if p.is_dir()];run=max(directories,key=lambda p:p.stat().st_mtime_ns) if directories else None
 state=subprocess.run(['systemctl','is-active','rml24-integrated'],stdout=subprocess.PIPE,universal_newlines=True).stdout.strip();out=dict(boot_id=boot,release=str(root),service=state,boot_cmdline=Path('/proc/cmdline').read_text().strip(),physical_display_confirmed=False)
 if not run:return dict(out,ready=False,reason='no run yet')
 children=json.loads((run/'children.json').read_text()) if (run/'children.json').exists() else [];alive={}
 for child in children:
  p=Path('/proc')/str(child['pid'])/'cmdline';alive[child['role']]=p.exists() and p.read_bytes().decode().rstrip('\0').split('\0')==list(map(str,child['argv']))
 logs={name:(run/(name+'.log')).read_text(errors='replace') if (run/(name+'.log')).exists() else '' for name in ('rx','ui','npu')};out.update(run=str(run),alive=alive,rx_ready='STANDALONE_READY' in logs['rx'],ui_fb_ready='UI_FB_READY' in logs['ui'],npu_ready='NPU_STREAM_READY' in logs['npu'])
 out['ready']=state=='active' and all(alive.get(x) for x in ('rx','ui','npu')) and all(out[x] for x in ('rx_ready','ui_fb_ready','npu_ready'));out['tail']={name:value.splitlines()[-2:] for name,value in logs.items()};return out
