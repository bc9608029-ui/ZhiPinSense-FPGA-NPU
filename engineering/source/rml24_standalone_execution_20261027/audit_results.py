import gzip,json,re
from pathlib import Path
r=Path(__file__).parent
e=json.loads(gzip.decompress((r/'board_evidence.json.gz').read_bytes()))
clock=json.loads((r/'clock_sync_before.json').read_text(encoding='utf-8-sig'))
offset=int(clock['offset_ns'])
checks=[]
for name,item in e.items():
    if not isinstance(item,dict) or 'records' not in item or 'final.json' not in item:continue
    f=item['final.json'];lines='\n'.join(item['log_tail'])
    npu=re.search(r'NPU_STREAM_STOP frames=(\d+) apply=(\d+) reset=(\d+) discipline=(\d+)',lines)
    checks.append(dict(run=name,check='radio_restore',passed=f['restore_errors']==[]))
    checks.append(dict(run=name,check='npu_accounting',passed=bool(npu) and
                       int(npu[1])==8*f['valid'] and int(npu[2])==1 and int(npu[4])==1 and
                       int(npu[3])==max(0,int(npu[1])-1)))
    if name!='negative01':
        checks.append(dict(run=name,check='ui_delivery',passed=f['ui_failed']==0))
    tx=r/(name+'_tx')
    if not (tx/'events_private.jsonl').exists() or not (tx/'restore.json').exists():continue
    events=[json.loads(x) for x in (tx/'events_private.jsonl').read_text().splitlines()]
    plan=json.loads((tx/'plan_private.json').read_text())
    warmup=tx/'warmup.json'
    start=json.loads(warmup.read_text())['start_ns'] if warmup.exists() else events[0]['start_ns']
    end=events[-1]['end_ns']
    false=[v['frame_id'] for v in item['records'] if v['finite'] and
           (v['capture_time_ns']+offset<start-500000000 or v['capture_time_ns']+offset>end+1000000000)]
    checks.append(dict(run=name,check='mute_false_classifications',passed=not false,frame_ids=false))
    checks.append(dict(run=name,check='tx_restore',passed=json.loads((tx/'restore.json').read_text())==[]))
    checks.append(dict(run=name,check='complete_tx',passed=len(events)==len(plan['records'])))
summary=dict(checks=checks,passed=sum(v['passed'] for v in checks),total=len(checks))
(r/'RESULT_AUDIT.json').write_text(json.dumps(summary,indent=2))
print(json.dumps({k:v for k,v in summary.items() if k!='checks'}))
for c in checks:
    if not c['passed']:print('NOT_PASS',c)
