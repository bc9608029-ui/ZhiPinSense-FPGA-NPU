import argparse,json
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--board',required=True);ap.add_argument('--expected',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
b=json.loads(Path(a.board).read_text());e=json.loads(Path(a.expected).read_text());expected={r['seq']:r for r in e['records']};rows=b['records'];assert len({r['seq'] for r in rows})==len(rows);assert all(r['seq'] in expected for r in rows);got={r['seq']:r for r in rows}
summary=dict(n=len(expected),received=len(rows),complete=len(rows)==len(expected),arms={},fixes=[],regressions=[],records=[])
for arm in ['baseline','candidate']:
 correct=failures=0;per_class=[dict(class_index=c,class_name=next(r['class_name'] for r in expected.values() if r['class_index']==c),total=0,correct=0,failures=0) for c in range(24)]
 for seq,t in expected.items():
  r=got.get(seq,{}).get('arms',{}).get(arm,{});pred=r.get('pred');valid=isinstance(pred,int) and 0<=pred<24 and 'error' not in r;ok=valid and pred==t['class_index'];correct+=int(ok);failures+=int(not valid);per_class[t['class_index']]['total']+=1;per_class[t['class_index']]['correct']+=int(ok);per_class[t['class_index']]['failures']+=int(not valid)
 summary['arms'][arm]=dict(correct=correct,total=len(expected),accuracy=correct/len(expected),failures=failures,per_class=per_class)
for seq,t in expected.items():
 preds={arm:got.get(seq,{}).get('arms',{}).get(arm,{}).get('pred') for arm in ['baseline','candidate']};r=dict(seq=seq,class_index=t['class_index'],class_name=t['class_name'],seed=t['seed'],**preds);summary['records'].append(r)
 if preds['baseline']!=t['class_index'] and preds['candidate']==t['class_index']:summary['fixes'].append(r)
 if preds['baseline']==t['class_index'] and preds['candidate']!=t['class_index']:summary['regressions'].append(r)
summary['candidate_clears_strict_no_regression_gate']=summary['complete'] and not summary['regressions'] and summary['arms']['candidate']['correct']>=summary['arms']['baseline']['correct']
Path(a.out).write_text(json.dumps(summary,indent=2));print(json.dumps({k:v for k,v in summary.items() if k not in ['arms','records']}));print('ARMS',[(k,v['correct'],v['total'],v['failures']) for k,v in summary['arms'].items()]);print('GMSK',[(k,v['per_class'][22]['correct'],v['per_class'][22]['total']) for k,v in summary['arms'].items()])