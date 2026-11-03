import json
from pathlib import Path
r=Path('/root/rml24_mainchain_diagnostic_20261028')
old={v['frame_id']:v for v in json.loads((r/'mean_replay01/results.json').read_text())};new={v['frame_id']:v for v in json.loads((r/'allclass_rms_replay04/results.json').read_text())};assert len(new)==613
labels=json.loads((r/'offline_development_labels.json').read_text());paired=[]
for v in labels:
 f=v['frame_id'];a=old.get(f);b=new.get(f)
 if not a or not b:continue
 paired.append(dict(v,old_pred=a['result']['pred'],new_pred=b['result']['pred'],old_correct=a['result']['pred']==v['label'],new_correct=b['result']['pred']==v['label']))
first=[min([v for v in paired if v['event_index']==i],key=lambda v:v['frame_id']) for i in range(48)]
out=dict(kind='DEVELOPMENT_ONLY_NOT_NEW_RF',stable_captures=len(paired),old_correct=sum(v['old_correct'] for v in paired),new_correct=sum(v['new_correct'] for v in paired),fixes=sum(not v['old_correct'] and v['new_correct'] for v in paired),regressions=sum(v['old_correct'] and not v['new_correct'] for v in paired),first_denominator=48,old_first_correct=sum(v['old_correct'] for v in first),new_first_correct=sum(v['new_correct'] for v in first),changed=[v for v in paired if v['old_pred']!=v['new_pred']])
(r/'allclass_rms_comparison.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
