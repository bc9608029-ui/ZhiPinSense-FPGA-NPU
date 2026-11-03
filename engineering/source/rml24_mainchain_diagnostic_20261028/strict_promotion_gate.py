"""Decision-only gate. Recompute every row; no hardware actions or deployment."""
import argparse,json
from pathlib import Path
def checked(path):
    x=json.loads(Path(path).read_text(encoding='utf-8'));rows=x.get('rows')
    if x.get('denominator')!=240 or not isinstance(rows,list) or len(rows)!=240:raise ValueError('fixed denominator/rows must be 240')
    if sorted(v.get('index',-1) for v in rows)!=list(range(240)):raise ValueError('duplicate or missing indices')
    for v in rows:
        if type(v.get('label')) is not int or not 0<=v['label']<24:raise ValueError('invalid label')
        if type(v.get('pred')) is not int or not -1<=v['pred']<24:raise ValueError('invalid prediction')
        if 'chosen_frame' not in v:raise ValueError('capture identity missing')
        if v['chosen_frame'] is None and v['pred']!=-1:raise ValueError('missing capture has a prediction')
    correct=sum(v['pred']==v['label'] for v in rows)
    missing=sum(v['chosen_frame'] is None for v in rows)
    if correct!=x.get('correct') or missing!=x.get('missing'):raise ValueError('summary counters do not match rows')
    return x
def evaluate(bf,bs,cf,cs):
    reasons=[]
    try:
        data=[checked(p) for p in [bf,bs,cf,cs]]
        for name,b,c in [('fixed',data[0],data[2]),('scan',data[1],data[3])]:
            if c['missing']:reasons.append(name+':missing')
            if c['correct']<b['correct']:reasons.append(name+':regression')
            for old,new in zip(sorted(b['rows'],key=lambda v:v['index']),sorted(c['rows'],key=lambda v:v['index'])):
                if old['label']!=new['label'] or old.get('file')!=new.get('file'):
                    reasons.append(name+':sample_identity_changed');break
    except (ValueError,KeyError,TypeError) as exc:reasons.append('invalid_evidence:'+str(exc))
    return dict(verdict='DO_NOT_PROMOTE' if reasons else 'PROMOTION_CANDIDATE',reasons=reasons,
                note='Decision only; UI, source freeze and user approval remain separate requirements')
if __name__=='__main__':
    p=argparse.ArgumentParser()
    for arg in ['baseline-fixed','baseline-scan','candidate-fixed','candidate-scan','out']:p.add_argument('--'+arg,required=True)
    a=p.parse_args();v=evaluate(a.baseline_fixed,a.baseline_scan,a.candidate_fixed,a.candidate_scan)
    Path(a.out).write_text(json.dumps(v,indent=2),encoding='utf-8');print(v['verdict'])
    raise SystemExit(2 if v['reasons'] else 0)
