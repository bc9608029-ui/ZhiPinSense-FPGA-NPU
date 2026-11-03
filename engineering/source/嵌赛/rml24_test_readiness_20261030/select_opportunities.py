"""PC-only pre-inference selection; exported IDs contain no ground truth."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse,json
from common import read,write,sha
from parameter_score import score,verify_clock_bracket
def main():
 p=argparse.ArgumentParser()
 for name in ['plan','captures','tx-events','clock-pre','clock-post','out']:p.add_argument('--'+name,type=Path,required=True)
 a=p.parse_args();lines=lambda f:[json.loads(s) for s in f.read_text().splitlines() if s.strip()]
 events=lines(a.tx_events)
 if any(e.get('plan_sha256')!=sha(a.plan) for e in events):raise ValueError('plan identity')
 plan=read(a.plan);pre=read(a.clock_pre);post=read(a.clock_post)
 verify_clock_bracket(plan,pre,post)
 r=score(plan,lines(a.captures),[],events,pre,post)
 ids=[v['record_id'] for v in r['rows'] if v['record_id'] is not None]
 if a.out.exists():raise ValueError('fresh output required')
 write(a.out,dict(record_ids=ids,denominator=r['denominator'],plan_sha256=sha(a.plan),
                  capture_manifest_sha256=sha(a.captures),selection='timestamps only, before inference'))
 print('SELECTED='+str(len(ids))+' EXPECTED='+str(r['denominator']))
if __name__=='__main__':main()
