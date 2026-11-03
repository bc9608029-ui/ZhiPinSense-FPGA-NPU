import gzip,hashlib,json
from pathlib import Path
import numpy as np
from repeat_mean_candidate import preprocess
r=Path(__file__).parent
diag=json.loads((r/'IQ_DIAGNOSTIC.json').read_text(encoding='utf-8'))
replay=json.loads(gzip.decompress((r/'mean_replay01.json.gz').read_bytes()))
baseline={v['frame_id']:v for v in diag['rows']};new={v['frame_id']:v for v in replay['results']}
if len(new)!=613:raise RuntimeError('Incomplete replay')
for index,v in new.items():
    path=r/'board/diag_fixed01/evidence'/('%06d.inputs.bin'%index)
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=v['source_input_sha256']:raise RuntimeError('Replay source mismatch')
    tensor=np.frombuffer(raw,dtype='<f4').reshape(8,2,1024)
    if hashlib.sha256(preprocess(tensor).tobytes()).hexdigest()!=v['candidate_input_sha256']:
        raise RuntimeError('Candidate implementation differs from replay')
paired=[]
for index,v in baseline.items():
    if v['event_index'] is None:continue
    nv=new.get(index)
    paired.append(dict(frame_id=index,event_index=v['event_index'],label=v['label'],
          baseline_pred=v['pred'],candidate_pred=nv['result']['pred'] if nv else -1,
          baseline_correct=v['correct'],candidate_correct=bool(nv and nv['result']['pred']==v['label'])))
first=[]
for event in range(48):
    g=[v for v in paired if v['event_index']==event]
    if not g:first.append(dict(event_index=event,baseline_correct=False,candidate_correct=False,missing=True))
    else:first.append(min(g,key=lambda v:v['frame_id']))
summary=dict(kind='DEVELOPMENT_REPLAY_ONLY_NOT_INDEPENDENT_RF',all_valid_replayed=len(new),
             stable_captures=len(paired),baseline_capture_correct=sum(v['baseline_correct'] for v in paired),
             candidate_capture_correct=sum(v['candidate_correct'] for v in paired),
             fixes=sum(not v['baseline_correct'] and v['candidate_correct'] for v in paired),
             regressions=sum(v['baseline_correct'] and not v['candidate_correct'] for v in paired),
             first_capture_denominator=48,baseline_first_correct=sum(v['baseline_correct'] for v in first),
             candidate_first_correct=sum(v['candidate_correct'] for v in first),
             npu_stop=replay['npu_stop'],first=first,paired=paired)
(r/'MEAN_CANDIDATE_COMPARISON.json').write_text(json.dumps(summary,indent=2))
print(json.dumps({k:v for k,v in summary.items() if k not in ['first','paired']},indent=2))
