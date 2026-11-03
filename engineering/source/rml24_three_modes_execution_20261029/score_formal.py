import argparse,gzip,json,re,sys
from pathlib import Path
r=Path(__file__).parent;sys.path.insert(0,str(r.parent/'rml24_standalone_execution_20261027'));from scoring_core import score
p=argparse.ArgumentParser();p.add_argument('name');a=p.parse_args();n=24 if a.name=='formal_sweep24_01' else 240
v=json.loads(gzip.decompress((r/'formal_evidence.json.gz').read_bytes()))[a.name];events=[json.loads(x) for x in (r/(a.name+'_tx/events_private.jsonl')).read_text().splitlines()];plan=json.loads((r/(a.name+'_tx/plan_private.json')).read_text());assert len(events)==len(plan['records'])==n
for i,(e,q) in enumerate(zip(events,plan['records'])):assert e['index']==i and all(e[k]==q[k] for k in ['seq','file','source_sha256'])
assert json.loads((r/(a.name+'_tx/restore.json')).read_text())==[];assert v['final']['restore_errors']==[] and v['supervisor']['clean_stop'] and not v['supervisor']['stop_errors'];assert all(x['repeat_average']==8 for x in v['rows'] if x['finite'])
m=re.search(r'frames=(\d+) apply=(\d+) reset=(\d+) discipline=(\d+)',' '.join(v['npu_stop']));assert m and int(m[1])==v['final']['valid']*8 and int(m[2])==1 and int(m[3])==max(0,int(m[1])-1) and int(m[4])==1
clock=json.loads((r/(a.name+'_clock.json')).read_text(encoding='utf-8-sig'));offset=int(clock['offset_ns']);records=v['rows'];method='ORIGINAL_FIRST_CAPTURE_WINDOW'
if n==24:
 method='FIRST_COVERAGE_OPPORTUNITY_WITHIN_1152KHZ_REGARDLESS_DETECTION_OR_PREDICTION';hz=int(plan['center_hz']);records=[x for x in records if x['scan_steps'] and abs(float(x['scan_steps'][0]['lo_hz'])-hz)<=1152000]
rows=score(events,records,offset)
if n==24:
 by={x['frame_id']:x for x in records}
 for x in rows:
  chosen=by.get(x['chosen_frame']);x['frequency_correct']=bool(chosen and abs(chosen['center_hz']-int(plan['center_hz']))<=10000);x['correct']=x['correct'] and x['frequency_correct']
out=dict(kind='NEW_RF_EXISTING_FROZEN_WAVEFORMS_NOT_UNSEEN_GENERALIZATION',name=a.name,denominator=n,correct=sum(x['correct'] for x in rows),missing=sum(x['chosen_frame'] is None for x in rows),rejected=sum(x['chosen_frame'] is not None and x['pred']==-1 for x in rows),misclassified=sum(x['chosen_frame'] is not None and x['pred']!=-1 and not x['correct'] for x in rows),method=method,clock_uncertainty_ms=clock['uncertainty_ms'],rows=rows)
(r/(a.name+'_score.json')).write_text(json.dumps(out,indent=2));print(json.dumps({k:x for k,x in out.items() if k!='rows'}),flush=True)
