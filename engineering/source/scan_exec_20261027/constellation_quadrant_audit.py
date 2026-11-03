import pathlib,json,numpy as np
p=pathlib.Path('/root/rml24_scan_execution_20261027');rows=[]
for name in ['ui_interactive_r2','centered_wide_v2']:
 for line in (p/name/'capture/ui_events.jsonl').read_text().splitlines():
  e=json.loads(line)
  if not e.get('iq_valid'):continue
  x=np.asarray(e['iq_i16_interleaved']).reshape(-1,2);f=float(np.mean((x[:,0]>=0)&(x[:,1]>=0)))
  if f>=.98:rows.append({'run':name,'seq':e['frame_id'],'predicted_class':e['prediction']['class_name'],'upper_right_fraction':f,'mean_i':float(x[:,0].mean()),'mean_q':float(x[:,1].mean()),'std_i':float(x[:,0].std()),'std_q':float(x[:,1].std())})
(p/'constellation_quadrant_audit.json').write_text(json.dumps(rows,indent=2));print('QUADRANT_AUDIT_READY',len(rows))