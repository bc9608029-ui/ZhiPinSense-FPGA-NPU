import json,tarfile,io
from pathlib import Path
r=Path(r'E:\rml24_gapfix_execution_20261028');p=json.loads((r/'gmsk_dev02_tx/plan_private.json').read_text());dataset=r.parent/'嵌赛/amr_rescue_gmsk_candidate_20261026/development_seed4100000'
with tarfile.open(str(r/'gmsk_clean_blind.tar.gz'),'w:gz') as t:
 for i,v in enumerate(p['records']):
  data=(dataset/v['file']).read_bytes();m=tarfile.TarInfo('%02d.bin'%i);m.size=len(data);t.addfile(m,io.BytesIO(data))
(r/'gmsk_clean_map_private.json').write_text(json.dumps(p['records'],indent=2))
