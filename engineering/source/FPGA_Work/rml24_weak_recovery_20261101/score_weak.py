from pathlib import Path
import json
base=Path('/root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031');r=Path('/root/rml24_weak_adaptive_classification_20261101/CLASSIFICATION_RESULT.json')
if not r.exists():print('WAIT');raise SystemExit(0)
truth={x['m']:x for x in json.loads((base/'WEAK_SELECTED.json').read_text())};rows=json.loads(r.read_text())['rows'];out=[]
for g in (-70,-60,-40):
 group=[x for x in rows if truth[x['capture_mono_ns']]['gain']==g];out.append(dict(gain=g,total=len(group),recovered=sum(x['recovered'] for x in group),correct=sum(x['recovered'] and x['prediction']['pred']==truth[x['capture_mono_ns']]['expected'] for x in group)))
print(json.dumps(out));Path('/root/rml24_weak_recovery_20261101/ADAPTIVE_CLASSIFICATION_SCORE.json').write_text(json.dumps(out,indent=2))
