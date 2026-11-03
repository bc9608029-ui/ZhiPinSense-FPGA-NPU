from pathlib import Path
import json,hashlib,re,shutil,subprocess,time,os
out=Path('/root/rml24_adaptation_archive_20261101');base=Path('/root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031');proof=json.loads((base/'ARCHIVE_PC_VERIFIED.json').read_text());manifest=out/'MANIFEST.json';meta=json.loads(manifest.read_text())
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
assert proof['passed'] and proof['manifest_sha256']==sha(manifest) and proof['archive_sha256']==meta['archive_sha256'] and proof['verified_files']==len(meta['files']);archive=out/'research_iq.tar.gz';assert sha(archive)==proof['archive_sha256'];allowed={'rml24_weak_bandwidth_rf_20261101','rml24_gainfreeze_range_paired_20261101','rml24_weak_adaptive_rf_20261101'};targets=[]
for rel,info in meta['files'].items():
 f=Path('/root')/rel
 if not re.fullmatch(r'raw_[0-9]+\.npy',f.name):continue
 assert Path(rel).parts[0] in allowed and not f.is_symlink() and Path('/root')/Path(rel).parts[0] in f.resolve().parents
 if f.exists():assert f.is_file() and sha(f)==info['sha256'];targets.append(f)
assert targets;freed=sum(f.stat().st_size for f in targets);(out/'CLEANUP_PLANNED.json').write_text(json.dumps(dict(raw_files=len(targets),raw_bytes=freed,pc_proof=proof),indent=2))
for f in targets:f.unlink()
archive.unlink();subprocess.run(['sync'],check=True);(out/'RAW_ARCHIVED_TO_PC.json').write_text(json.dumps(dict(raw_files=len(targets),freed_raw_bytes=freed,pc_archive=proof['computer_archive'],archive_sha256=proof['archive_sha256'],manifest_sha256=proof['manifest_sha256']),indent=2));assert shutil.disk_usage('/').free>1024**3;assert not Path('/var/lib/rml24-fpga-shared-guard/reset_required.json').exists();subprocess.run(['systemctl','reset-failed','rml24-integrated'],check=True);subprocess.run(['systemctl','start','rml24-integrated'],check=True)
ready=False;health={}
for _ in range(40):
 try:
  pid=int(subprocess.check_output(['systemctl','show','rml24-integrated','-p','MainPID','--value']).strip());args=Path('/proc/%d/cmdline'%pid).read_bytes().decode().strip('\0').split('\0');run=Path(args[args.index('--run')+1]);children=json.loads((run/'children.json').read_text());alive={c['role']:Path('/proc/%d/cmdline'%c['pid']).exists() and Path('/proc/%d/cmdline'%c['pid']).read_bytes().decode().strip('\0').split('\0')==list(map(str,c['argv'])) for c in children};logs={k:(run/(k+'.log')).read_text(errors='replace') for k in ('npu','ui','rx')};ready=all(alive.get(k) for k in ('npu','ui','rx')) and 'NPU_STREAM_READY' in logs['npu'] and 'UI_FB_READY' in logs['ui'] and 'STANDALONE_READY' in logs['rx'];health=dict(ready=ready,run=str(run),alive=alive,free_bytes=shutil.disk_usage('/').free,formal_release=str(Path('/opt/rml24-integrated/current').resolve()))
  if ready:break
 except (OSError,ValueError,KeyError):pass
 time.sleep(.5)
(out/'RESTORED_HEALTH.json').write_text(json.dumps(health,indent=2));assert ready,health;print('RESTORED_FORMAL_READY '+json.dumps(health),flush=True)
