#!/usr/bin/env python3
"""Promotion gate: never replaces services; only emits a decision."""
from __future__ import annotations
import argparse,json
from pathlib import Path

def read(p): return json.loads(p.read_text(encoding='utf-8'))
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--baseline-fixed',type=Path,required=True); ap.add_argument('--baseline-scan',type=Path,required=True)
    ap.add_argument('--candidate-fixed',type=Path,required=True); ap.add_argument('--candidate-scan',type=Path,required=True); ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args(); xs={k:read(getattr(a,k)) for k in ('baseline_fixed','baseline_scan','candidate_fixed','candidate_scan')}
    reasons=[]
    for mode in ('fixed','scan'):
        b,c=xs['baseline_'+mode],xs['candidate_'+mode]
        if int(c.get('denominator',-1))!=240 or int(c.get('missing',1))!=0: reasons.append(mode+':incomplete')
        if int(c.get('correct',-1))<int(b.get('correct',9999)): reasons.append(mode+':regression')
    verdict='PROMOTION_CANDIDATE' if not reasons else 'DO_NOT_PROMOTE'
    out={'verdict':verdict,'reasons':reasons,'note':'decision only; no deployment mutation'}
    a.out.write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8'); print(verdict); raise SystemExit(0 if verdict=='PROMOTION_CANDIDATE' else 2)
if __name__=='__main__': main()
