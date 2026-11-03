import sys,json,hashlib
from pathlib import Path
import numpy as np
sys.path.insert(0,'/root/rml24_stage7_execution_20261027/final/rml24_final/runtime')
from ui_event import _display_payload
out=Path('/root/rml24_stage7_execution_20261027');rows=[]
for name in ('rml24_stage7_formal_r1_20261027','rml24_stage7_formal_r2_20261027'):
 p=Path('/root')/name/'capture';events={e['frame_id']:e for e in map(json.loads,(p/'ui_events.jsonl').read_text().splitlines())};records=json.loads((p/'results.json').read_text())['records'];assert len(events)==len(records)==240
 for rec in records:
  seq=rec['seq'];e=events[seq];arm=rec['arms']['candidate'];data=(p/('%04d.candidate.inputs.bin'%seq)).read_bytes();sha=hashlib.sha256(data).hexdigest();x=np.frombuffer(data,dtype='<f4').reshape(8,2,1024);display=_display_payload(x);ok=sha==arm['input_sha256']==e['model_input_sha256'] and e['prediction']['index']==arm['pred'] and all(e[k]==v for k,v in display.items());rows.append(dict(run=name,seq=seq,pass_same_tensor=ok))
doc=dict(total=len(rows),passed=sum(x['pass_same_tensor'] for x in rows),records=rows);(out/'ui_same_tensor_audit.json').write_text(json.dumps(doc,indent=2));print('UI_SAME_TENSOR_AUDIT',doc['passed'],doc['total']);assert doc['passed']==doc['total']==480