import argparse,gzip,json
from pathlib import Path
from scoring_core import score
p=argparse.ArgumentParser();p.add_argument('run');a=p.parse_args()
r=Path(__file__).parent
e=json.loads(gzip.decompress((r/'board_evidence.json.gz').read_bytes()))[a.run]
clock=json.loads((r/'clock_sync_before.json').read_text(encoding='utf-8-sig'))
offset=int(clock['offset_ns'])
events=[json.loads(x) for x in (r/(a.run+'_tx')/'events_private.jsonl').read_text().splitlines()]
plan=json.loads((r/(a.run+'_tx')/'plan_private.json').read_text())
if len(events)!=len(plan['records']) or not (r/(a.run+'_tx')/'restore.json').exists():
    raise RuntimeError('TX still running or incomplete: do not publish a partial denominator')
if 'final.json' not in e:
    raise RuntimeError('RX final evidence not collected yet')
for index,(actual,expected) in enumerate(zip(events,plan['records'])):
    if actual['index']!=index or any(actual[k]!=expected[k] for k in ['seq','file','source_sha256']):
        raise RuntimeError('TX events differ from frozen plan')
scored=score(events,e['records'],offset)
result=dict(kind='INDEPENDENT_TX_RX_FIRST_CAPTURE_SCORE',run=a.run,
            denominator=len(events),correct=sum(v['correct'] for v in scored),
            missing=sum(v['chosen_frame'] is None for v in scored),
            clock_uncertainty_ms=clock['uncertainty_ms'],
            rows=scored)
warmup=r/(a.run+'_tx')/'warmup.json'
if warmup.exists():
    w=json.loads(warmup.read_text())
    first=min((v['capture_time_ns']+offset for v in e['records']
               if v['finite'] and v['capture_time_ns']+offset>=w['start_ns']),default=None)
    result['first_valid_capture_after_warmup_start_sec']=(first-w['start_ns'])/1e9 if first else None
    result['warmup_sec']=plan['warmup_sec']
(r/(a.run+'_score.json')).write_text(json.dumps(result,indent=2))
print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))
