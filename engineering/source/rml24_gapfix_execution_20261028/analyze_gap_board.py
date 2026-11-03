import json
from pathlib import Path
r=Path('/root/rml24_gapfix_execution_20261028')
rows=[json.loads(x) for x in (r/'gapfix_scan01/capture/records.jsonl').read_text().splitlines()]
indices=[i for i,v in enumerate(rows) if v['elapsed_ms']>3000]
keep=set()
for i in indices:keep.update(range(max(0,i-6),min(len(rows),i+3)))
result={'long_count':len(indices),'rows':[rows[i] for i in sorted(keep)]}
(r/'scan_gap_analysis.json').write_text(json.dumps(result,indent=2))
for i in sorted(keep):
 v=rows[i];print(json.dumps(dict(frame=v['frame_id'],capture_ns=v['capture_time_ns'],elapsed_ms=v['elapsed_ms'],error=v['candidate'].get('error'),steps=v['scan_steps'])))
