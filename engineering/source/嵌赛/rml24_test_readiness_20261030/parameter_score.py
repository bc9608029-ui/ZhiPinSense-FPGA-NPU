"""PC-only truth join: choose capture by time before inspecting any prediction."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse,json
from common import read,write,sha

def verify_clock_bracket(plan,pre,post):
 if pre.get('kind')!='BOARD_MINUS_PC_CLOCK_BOUND' or post.get('kind')!='BOARD_MINUS_PC_CLOCK_BOUND':
  raise ValueError('clock observation identity')
 if not pre.get('samples') or not post.get('samples'):raise ValueError('clock samples required')
 if max(s['pc_after_ns'] for s in pre['samples'])>=plan['start_ns']:raise ValueError('pre clock probe is not before TX plan')
 if min(s['pc_before_ns'] for s in post['samples'])<=plan['end_ns']:raise ValueError('post clock probe is not after TX plan')

def choose(rows,start,end,lo,hi,margin):
 # For any admissible board-minus-PC offset, entire capture must lie within TX.
 eligible=[r for r in rows if r['capture_start_ns']-hi>=start+margin
           and r['capture_end_ns']-lo<=end-margin]
 target=(start+end)//2
 return min(eligible,key=lambda r:(abs((r['capture_start_ns']+r['capture_end_ns'])//2-(lo+hi)//2-target),r['record_id']),default=None)

def score(plan,captures,replays,events,pre,post):
 lo=min(pre['lo_ns'],post['lo_ns']);hi=max(pre['hi_ns'],post['hi_ns'])
 if lo>hi or hi-lo>200_000_000:raise ValueError('clock bound >200ms: measurement invalid')
 # Endpoint sampling assumes no unobserved clock step; RX wall/monotonic checks enforce locally.
 def unique(rows,key):
  out={}
  for r in rows:
   if r[key] in out:raise ValueError('duplicate '+key)
   out[r[key]]=r
  return out
 rep=unique(replays,'record_id');ev=unique(events,'opportunity');unique(captures,'record_id')
 result=[];correct={str(n):0 for n in (1,2,4,8)};used=set()
 for p in plan['rows']:
  e=ev.get(p['opportunity']);selected=None
  if e and e['end_ns']>e['start_ns']:
   if e['start_ns']<p['start_ns'] or e['start_ns']-p['start_ns']>250_000_000:raise ValueError('TX start outside schedule')
   selected=choose(captures,e['start_ns'],e['end_ns'],lo,hi,plan['margin_ns'])
  row=dict(opportunity=p['opportunity'],label=p['label'],record_id=None,pred={str(n):-1 for n in (1,2,4,8)})
  if selected:
   rid=selected['record_id']
   if rid in used:raise ValueError('capture reused across opportunities')
   used.add(rid);row['record_id']=rid;r=rep.get(rid,{})
   if r and r['raw_sha256']!=selected['sha256']:raise ValueError('replay/capture SHA mismatch')
   for n in correct:
    arm=r.get('arms',{}).get(n,{})
    pred=arm.get('pred',-1) if arm.get('valid') else -1
    if pred is None:raise ValueError('tensors only: NPU inference not performed')
    row['pred'][n]=pred;correct[n]+=int(pred==p['label'])
  result.append(row)
 return dict(denominator=len(plan['rows']),correct=correct,rows=result,
             selected=sum(r['record_id'] is not None for r in result),
             warning='fixed source set under frozen conditions; no arbitrary-RF or shortened-TX claim')

def main():
 p=argparse.ArgumentParser()
 for n in ['plan','captures','replays','tx-events','clock-pre','clock-post','capture-summary','rx-restore','tx-restore','out']:p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args()
 lines=lambda path:[json.loads(s) for s in path.read_text().splitlines() if s.strip()]
 ev=lines(a.tx_events)
 if any(e.get('plan_sha256')!=sha(a.plan) for e in ev):raise ValueError('TX event plan binding mismatch')
 plan=read(a.plan);pre=read(a.clock_pre);post=read(a.clock_post)
 verify_clock_bracket(plan,pre,post)
 out=score(plan,lines(a.captures),lines(a.replays),ev,pre,post)
 summary=read(a.capture_summary);rx=read(a.rx_restore);tx=read(a.tx_restore)
 reasons=[]
 if summary.get('error') or summary.get('write_restore_errors'):reasons.append('RX_CAPTURE_OR_RESTORE_ERROR')
 if summary.get('raw_records')!=len(lines(a.captures)):reasons.append('RX_ROW_COUNT_MISMATCH')
 if rx.get('restore_verified') is not True:reasons.append('RX_RESTORE_UNVERIFIED')
 if tx.get('readback_verified') is not True or tx.get('write_restore_errors'):reasons.append('TX_RESTORE_UNVERIFIED')
 if len(ev)!=len(plan['rows']):reasons.append('TX_OPPORTUNITY_INCOMPLETE')
 if out['selected']!=out['denominator']:reasons.append('RX_OPPORTUNITY_INCOMPLETE')
 out.update(measurement_valid=not reasons,invalid_reasons=reasons)
 if a.out.exists():raise ValueError('fresh output required')
 write(a.out,out);print(json.dumps({k:v for k,v in out.items() if k!='rows'}))
 return 0 if not reasons else 2
if __name__=='__main__':sys.exit(main())
