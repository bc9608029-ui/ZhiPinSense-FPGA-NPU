from pathlib import Path
import json,hashlib,re
root=Path('/root/rml24_sweep_raw_diagnostic_20261101/runs/sweep6/capture').resolve();out=root.parent/'export';a=out/'sweep_raw_evidence.tar.gz';assert hashlib.sha256(a.read_bytes()).hexdigest()=='ac301c07797141d5791ec827e817ab181dac69e3d076e31958ecc11c8093fbee';m=json.loads((out/'MANIFEST.json').read_text());assert m['root']==str(root);selected=[]
for name,item in m['files'].items():
 if not re.fullmatch(r'[0-9]{6}[.](raw[.]npy|inputs[.]bin)',name):continue
 f=root/name;assert f.resolve().parent==root and not f.is_symlink();assert f.stat().st_size==item['size'] and hashlib.sha256(f.read_bytes()).hexdigest()==item['sha256'];selected.append(f)
assert selected
for f in selected:f.unlink()
a.unlink();(out/'CLEANUP_RECEIPT.json').write_text(json.dumps(dict(files=[f.name for f in selected],archive_removed=str(a),pc_archive_sha256='ac301c07797141d5791ec827e817ab181dac69e3d076e31958ecc11c8093fbee',metadata_preserved=True)));print('VERIFIED_DIAGNOSTIC_RAW_ARCHIVED',len(selected))
