"""Read-only proof that the four missing items follow long full-rescan gaps."""
from pathlib import Path
import gzip,json

ROOT=Path(r'F:\rml24_repeat_mean_validation_20261028')

def main():
    score=json.loads((ROOT/'candidate_scan01_score.json').read_text(encoding='utf-8'))
    missing=[r for r in score['rows'] if r['chosen_frame'] is None]
    assert [r['index'] for r in missing] == [65,66,121,122]
    evidence=json.load(gzip.open(ROOT/'evidence.json.gz','rt',encoding='utf-8'))['candidate_scan01']['records']
    gaps=[]
    for a,b in zip(evidence,evidence[1:]):
        if not a['capture_time_ns'] or not b['capture_time_ns']:
            continue
        dt=(b['capture_time_ns']-a['capture_time_ns'])/1e9
        if dt>10:
            gaps.append((a['frame_id'],b['frame_id'],dt,a['error']))
    # Exactly two >10 s stalls align with the two missing pairs. The preceding
    # record is a locked-frequency public-frame rejection, after which the old
    # three-miss policy launches the complete 11-point sweep.
    assert len(gaps)==2, gaps
    assert all(g[3]=='NO_VALID_PUBLIC_FRAME' for g in gaps), gaps
    print(json.dumps({'missing_indices':[r['index'] for r in missing],
                      'long_gaps':gaps,'conclusion':'FULL_RESCAN_STALL_CONFIRMED'},indent=2))

if __name__=='__main__': main()

