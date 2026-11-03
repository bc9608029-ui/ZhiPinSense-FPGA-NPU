from pathlib import Path
import json,hashlib,re,shutil
base=Path('/root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031');out=Path('/root/rml24_gain_headroom_archive_20261101');root=Path('/root/rml24_gain_only_clipguard_rf_20261101').resolve();proof=json.loads((base/'GAIN_ARCHIVE_VERIFIED.json').read_text());archive=out/'raw_gain_pairs.tar.gz';manifest=out/'MANIFEST.json';v=json.loads(manifest.read_text());assert v['root']==str(root) and proof['all_members_verified'] and proof['files']==len(v['files']);assert hashlib.sha256(archive.read_bytes()).hexdigest()==proof['archive_sha256'];assert hashlib.sha256(manifest.read_bytes()).hexdigest()==proof['manifest_sha256'];paths=[]
for name,entry in v['files'].items():
 assert re.fullmatch(r'pair_[0-9]+_(initial|final)[.]npy',name);f=root/name;assert f.resolve().parent==root and f.is_file() and not f.is_symlink();assert f.stat().st_size==entry['size'] and hashlib.sha256(f.read_bytes()).hexdigest()==entry['sha256'];paths.append(f)
for f in paths:f.unlink()
archive.unlink();result=dict(removed_raw_files=len(paths),pc_archive=proof['pc_archive'],archive_sha256=proof['archive_sha256'],free_bytes=shutil.disk_usage('/').free,metadata_models_boot_and_services_untouched=True);(out/'CLEANUP_RESULT.json').write_text(json.dumps(result,indent=2));print('VERIFIED_GAIN_RAW_ARCHIVED '+json.dumps(result),flush=True)
