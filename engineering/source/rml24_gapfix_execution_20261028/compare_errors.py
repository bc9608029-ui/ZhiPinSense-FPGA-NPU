import json
from pathlib import Path
r=Path(r'E:\rml24_gapfix_execution_20261028')
paths=[r.parent/'rml24_repeat_mean_validation_20261028/candidate_fixed02_score.json',r/'gapfix_fixed01_score.json',r/'fix2_fixed01_score.json',r/'fix2_scan02_score.json']
report={}
for p in paths:
 s=json.loads(p.read_text());bad=[v for v in s['rows'] if not v['correct']];report[p.stem]={'correct':s['correct'],'missing':s['missing'],'errors':bad}
print(json.dumps(report,indent=2));(r/'ERROR_COMPARISON.json').write_text(json.dumps(report,indent=2))
