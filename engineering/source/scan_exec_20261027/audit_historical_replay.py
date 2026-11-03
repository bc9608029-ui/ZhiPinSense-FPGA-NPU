import pathlib,json,numpy as np
root=pathlib.Path(__file__).parent
old=json.loads(pathlib.Path('E:/嵌赛/rml24_stage7_execution_20261027/waterfall_fix1_r1_results.json').read_text())['records'];new=json.loads((root/'historical_npu_replay.json').read_text())['records'];old={r['seq']:r['arms']['candidate'] for r in old};diff=[];sha=[];logit=[]
for r in new:
 a=old[r['seq']]
 if r['pred']!=a['pred']:diff.append(r['seq'])
 if r['input_sha256']!=a['input_sha256']:sha.append(r['seq'])
 logit.append(float(np.max(np.abs(np.array(r['mean_logits'])-a['mean_logits']))))
report={'records':len(new),'prediction_differences':diff,'input_hash_differences':sha,'max_abs_mean_logit_difference':max(logit),'pass':len(new)==240 and not diff and not sha and max(logit)==0}
(root/'historical_npu_replay_audit.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))