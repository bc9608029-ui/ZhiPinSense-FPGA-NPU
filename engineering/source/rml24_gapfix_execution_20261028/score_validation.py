import argparse,gzip,json,re,sys
from pathlib import Path
r=Path(__file__).parent;sys.path.insert(0,str(r.parent/'rml24_standalone_execution_20261027'))
from scoring_core import score
p=argparse.ArgumentParser();p.add_argument('run');a=p.parse_args()
e=json.loads(gzip.decompress((r/'evidence.json.gz').read_bytes()))[a.run]
if any(v['finite'] and v.get('repeat_average')!=8 for v in e['records']):raise RuntimeError('Candidate path not applied to every valid frame')
events=[json.loads(x) for x in (r/(a.run+'_tx/events_private.jsonl')).read_text().splitlines()]
plan=json.loads((r/(a.run+'_tx/plan_private.json')).read_text())
if len(events)!=240 or len(plan['records'])!=240:raise RuntimeError('Incomplete fixed denominator')
if not (r/(a.run+'_tx/restore.json')).exists():raise RuntimeError('TX has not finished')
for i,(v,q) in enumerate(zip(events,plan['records'])):
    if v['index']!=i or any(v[k]!=q[k] for k in ['seq','file','source_sha256']):raise RuntimeError('Plan/event mismatch')
clock=json.loads((r/(a.run+'_clock_before.json')).read_text(encoding='utf-8-sig'))
offset=int(clock['offset_ns']);rows=score(events,e['records'],offset)
stop=re.search(r'NPU_STREAM_STOP frames=(\d+) apply=(\d+) reset=(\d+) discipline=(\d+)','\n'.join(e['log_tail']))
if not stop or int(stop[1])!=e['final']['valid']*8 or int(stop[2])!=1 or int(stop[3])!=max(0,int(stop[1])-1) or int(stop[4])!=1:
    raise RuntimeError('NPU accounting not complete/consistent')
if e['final']['restore_errors']:raise RuntimeError('RX restoration failure')
if json.loads((r/(a.run+'_tx/restore.json')).read_text()):raise RuntimeError('TX restoration failure')
out=dict(kind='FROZEN_REPEAT_MEAN_V1_NEW_RF_SAME_EXISTING_240_SOURCES',run=a.run,
    denominator=240,correct=sum(v['correct'] for v in rows),missing=sum(v['chosen_frame'] is None for v in rows),
    clock_uncertainty_ms=clock['uncertainty_ms'],rows=rows)
(r/(a.run+'_score.json')).write_text(json.dumps(out,indent=2))
print(json.dumps({k:v for k,v in out.items() if k!='rows'}),flush=True)
