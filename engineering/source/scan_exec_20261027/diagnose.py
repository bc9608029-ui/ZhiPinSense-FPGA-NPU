import json,pathlib,numpy as np
root=pathlib.Path(__file__).parent
truth=json.loads(pathlib.Path('E:/嵌赛/rml24_stage7_execution_20261027/pc/rml24_final_stage7_pc_selftest/truth/expected_private.json').read_text(encoding='utf-8'))
t={r['seq']:r['class_index'] for r in truth['records']}
for name in ['fixed_r1','fixed_r2']:
 rows=json.loads((root/(name+'_results.json')).read_text())['records']
 errors=[]
 for r in rows:
  a=r['candidate']
  if a['pred']!=t[r['seq']]:errors.append({'seq':r['seq'],'truth':t[r['seq']],'pred':a['pred'],'cfo':a['cfo_hz'],'fir':a['fir_training_residual'],'head':a['head_reference_relative_error'],'gain':a['gain'],'dc':a['dc']})
 report={'errors':errors,'medians':{k:float(np.median([r['candidate'][k] for r in rows])) for k in ['cfo_hz','fir_training_residual','gain','dc']}}
 (root/(name+'_diagnostics.json')).write_text(json.dumps(report,indent=2))
 print(name,json.dumps(report))