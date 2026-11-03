from pathlib import Path
import json
root=Path('/root/rml24_samplerate_experiment_20261101');out=[]
for folder in ('attempt2','attempt3'):
 f=root/folder/'CLASSIFICATION_RESULT.json'
 if not f.exists():continue
 rows=json.loads(f.read_text())['rows']
 for fs in sorted(set(x['sample_rate'] for x in rows)):
  r=[x for x in rows if x['sample_rate']==fs];out.append(dict(attempt=folder,effective_fs=fs,hardware_fs=sorted(set(x['hardware_rate'] for x in r)),digital_only=r[0]['digital_only'],total=len(r),recovered=sum(x['recovered'] for x in r),preds=[x.get('prediction',{}).get('pred') for x in r]))
print(json.dumps(out));(root/'SUMMARY.json').write_text(json.dumps(out,indent=2))
