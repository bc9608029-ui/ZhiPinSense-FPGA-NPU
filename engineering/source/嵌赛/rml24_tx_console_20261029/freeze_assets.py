"""Copy one SHA-verified existing IQ payload per class for a portable console."""
from pathlib import Path
import json,hashlib,shutil
from tx_core import ROOT,WORKSPACE,CLASSES
source=WORKSPACE/'rml24_stage7_execution_20261027/pc/rml24_final_stage7_pc_selftest/dataset'
manifest=WORKSPACE/'rml24_final_integration1_work/pc_runtime/selftest_manifest_240.json'
rows=json.loads(manifest.read_text(encoding='utf8'))['records'];selected={}
for row in rows:
 label=int(Path(row['file']).stem.split('_')[0])
 if label not in selected:selected[label]=row
assert set(selected)==set(range(24))
dest=ROOT/'assets';dest.mkdir(exist_ok=True);out=[]
for label in range(24):
 row=selected[label];raw=(source/row['file']).read_bytes()
 assert hashlib.sha256(raw).hexdigest()==row['source_sha256']
 shutil.copyfile(source/row['file'],dest/row['file'])
 out.append(dict(seq=label,file=row['file'],source_sha256=row['source_sha256']))
(dest/'manifest_24.json').write_text(json.dumps(dict(kind='TX_CONSOLE_EXISTING_FROZEN_SUBSET',
 source_manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),records=out),indent=2),encoding='utf8')
print('FREEZE_ASSETS PASS classes=24 bytes_unchanged=YES')
