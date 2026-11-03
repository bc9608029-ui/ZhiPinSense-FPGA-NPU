import json,hashlib
from pathlib import Path
r=Path('/root/rml24_gapfix_execution_20261028')
rows=[json.loads(x) for x in (r/'fix2_smoke24/capture/records.jsonl').read_text().splitlines()]
counts=[sum(not s.get('locked_check',False) for s in v['scan_steps']) for v in rows]
assert max(counts)<=1
summary={'run':'fix2_smoke24','records':len(rows),'max_elapsed_ms':max(v['elapsed_ms'] for v in rows),'max_search_points_per_record':max(counts),'home_revisit_count':sum(s.get('home_revisit',False) for v in rows for s in v['scan_steps']),'longer_than_10s':sum(v['elapsed_ms']>10000 for v in rows),'receiver_sha256':hashlib.sha256((r/'candidate_fix2/rml24_final/board_runtime/standalone_receiver.py').read_bytes()).hexdigest()}
(r/'fix2_smoke_timing.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))
