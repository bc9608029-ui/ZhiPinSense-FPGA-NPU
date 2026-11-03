import json,pathlib,numpy as np
base=pathlib.Path('E:/嵌赛/rml24_stage7_execution_20261027')
cur=pathlib.Path(__file__).parent
out={}
for name,p in [('historical_r1',base/'waterfall_fix1_r1_results.json'),('historical_r2',base/'waterfall_fix1_r2_results.json'),('current_r1',cur/'fixed_r1_results.json'),('current_r2',cur/'fixed_r2_results.json'),('old_control',cur/'legacy_control_r1_results.json')]:
 rows=json.loads(p.read_text(encoding='utf-8'))['records']; arms=[r.get('candidate',r.get('arms',{}).get('candidate')) for r in rows]
 out[name]={k:dict(zip(['min','median','max'],map(float,np.quantile([a[k] for a in arms],[0,.5,1])))) for k in ['cfo_hz','training_residual','fir_training_residual','head_reference_relative_error','tail_reference_relative_error','tail_residual','gain','dc']}
 print(name,json.dumps({k:round(v['median'],5) for k,v in out[name].items()}))
(cur/'historical_comparison.json').write_text(json.dumps(out,indent=2))