from pathlib import Path
import json,numpy as np
root=Path('/root/rml24_fix3_1793441664/quiet/capture');live={x['frame_id']:x for x in [json.loads(s) for s in (root/'records.jsonl').read_text().splitlines()]}
replay=json.loads(Path('/root/rml24_clean_compare_1773394583/RESULT.json').read_text());out=[]
for record in replay['results']:
 for frame in record['frames']:
  a=np.asarray(live[frame['frame_id']]['candidate']['mean_logits']);b=np.asarray(frame['inference']['logits']);out.append(dict(frame_id=frame['frame_id'],exact=bool(np.array_equal(a,b)),max_abs=float(np.max(abs(a-b)))))
v=dict(count=len(out),exact=sum(x['exact'] for x in out),max_abs=max(x['max_abs'] for x in out),rows=out);Path('/root/rml24_same_input_npu_comparison.json').write_text(json.dumps(v,indent=2));print(json.dumps({k:x for k,x in v.items() if k!='rows'}))
