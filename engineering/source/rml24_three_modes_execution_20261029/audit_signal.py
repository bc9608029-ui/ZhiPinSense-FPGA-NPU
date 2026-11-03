import json,re
from pathlib import Path
r=Path('/root/rml24_three_modes_execution_20261029');out={}
for name in ['signal_fixed01','signal_lock01','signal_sweep01']:
 rows=[json.loads(x) for x in (r/name/'capture/records.jsonl').read_text().splitlines()];valid=[v for v in rows if v['candidate'].get('finite')];final=json.loads((r/name/'capture/final.json').read_text());sup=json.loads((r/name/'supervisor.json').read_text());steps=[s for v in rows for s in v['scan_steps']];indices=[s['scan_index'] for s in steps if 'scan_index' in s];stop=re.findall(r'NPU_STREAM_STOP[^\r\n]*',(r/name/'npu.log').read_text(errors='replace'))
 out[name]=dict(final=final,supervisor=sup,valid_prediction_counts={str(k):sum(v['candidate']['pred']==k for v in valid) for k in sorted(set(v['candidate']['pred'] for v in valid))},scan_indices=indices,npu_stop=stop)
out['history_text']=(r/'signal_history.txt').read_text();out['kind']='SINGLE_WAVEFORM_FUNCTIONAL_SHORT_TEST_NOT_ACCURACY_REGRESSION';(r/'SIGNAL_AUDIT.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
