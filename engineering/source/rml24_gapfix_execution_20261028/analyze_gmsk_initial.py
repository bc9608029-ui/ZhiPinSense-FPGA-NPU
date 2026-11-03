import json,collections
from pathlib import Path
r=Path('/root/rml24_mainchain_diagnostic_20261028/diag_gmsk02')
rows=[json.loads(x) for x in (r/'capture/records.jsonl').read_text().splitlines()]
valid=[v for v in rows if v['candidate'].get('finite')]
report={'valid':len(valid),'pred_histogram':dict(collections.Counter(v['candidate']['pred'] for v in valid)),'first_valid':[{'frame':v['frame_id'],'capture_ns':v['capture_time_ns'],'candidate':v['candidate']} for v in valid[:3]],'trace_count':len(list((r/'evidence').glob('*.trace.json')))}
(r/'initial_analysis.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
