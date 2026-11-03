import sys,json,hashlib,tarfile
from pathlib import Path
import numpy as np
sys.path.insert(0,'/root/amr_rescue_20261025')
sys.path.insert(0,'/root/rml24_stage7_execution_20261027/final/rml24_final/recovery')
import candidate_two_dc
out=Path('/root/rml24_stage7_execution_20261027');rows=[]
for run in ('amr_pair_validation_20261026_r1','amr_pair_validation_20261026_r2'):
 src=Path('/root')/run/'capture'
 for raw in sorted(src.glob('*.raw.npy')):
  seq=int(raw.name.split('.')[0]);x,meta=candidate_two_dc.recover(np.load(raw));data=np.stack([x.real,x.imag],axis=1).astype('<f4').tobytes();saved=(src/('%04d.candidate.inputs.bin'%seq)).read_bytes();rows.append(dict(run=run,seq=seq,equal=data==saved,replayed_sha256=hashlib.sha256(data).hexdigest(),saved_sha256=hashlib.sha256(saved).hexdigest()))
 doc=dict(kind='FROZEN_RAW_TO_TENSOR_BYTE_REPLAY',records=rows,passed=sum(x['equal'] for x in rows),total=len(rows))
 (out/'raw_replay_audit.json').write_text(json.dumps(doc,indent=2));print(run,len(rows),doc['passed'],flush=True)
assert len(rows)==480 and all(x['equal'] for x in rows)
with tarfile.open(out/'historical_raw_tensor_captures.tar.gz','w:gz',compresslevel=1) as t:
 for run in ('amr_pair_validation_20261026_r1','amr_pair_validation_20261026_r2'):
  src=Path('/root')/run/'capture'
  for p in sorted(src.iterdir()):
   if p.is_file() and (p.name.endswith('.raw.npy') or p.name.endswith('.candidate.inputs.bin') or p.name=='results.json'):t.add(p,arcname=run+'/'+p.name)
print('RAW_REPLAY_AND_ARCHIVE_COMPLETE',flush=True)