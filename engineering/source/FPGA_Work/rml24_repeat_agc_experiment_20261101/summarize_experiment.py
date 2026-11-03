from pathlib import Path
import json,collections
root=Path('/root/rml24_repeat_agc_experiment_20261101');d=json.loads((root/'CLASSIFICATION_RESULT.json').read_text());groups={}
for x in d['rows']:
 key=('variable_detected_'+str(x.get('metadata',{}).get('detected_repeats','reject'))) if x['folder'].endswith('variable_repeats') else ('agc_'+x['mode']+'_'+x['actual_gain']+'_'+x['bandwidth'])
 g=groups.setdefault(key,dict(total=0,recovered=0,preds={}));g['total']+=1
 if x['recovered']:
  g['recovered']+=1;p=str(x['prediction']['pred']);g['preds'][p]=g['preds'].get(p,0)+1
out=dict(groups=groups,classification_records=len(d['rows']),scope='Single BPSK reference, limited diagnostic; variable groups use detected counts, not truth-conditioned denominators');(root/'EXPERIMENT_SUMMARY.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
