"""Offline scoring only: never deploy private ground truth to RX board."""
import argparse,json
from pathlib import Path
ap=argparse.ArgumentParser()
ap.add_argument('--board-results',required=True)
ap.add_argument('--expected',required=True)
args=ap.parse_args()
rows=json.loads(Path(args.board_results).read_text())['records']
expected=json.loads(Path(args.expected).read_text())
truth={r['seq']:r for r in expected}
assert len(truth)==len(expected) and len(set(r['seq'] for r in rows))==len(rows)
assert all(r['seq'] in truth for r in rows)
correct=sum(r.get('pred')==truth[r['seq']]['class_index'] for r in rows)
print(json.dumps({'correct':correct,'total':len(expected),'accuracy':correct/len(expected),
                  'missing':len(expected)-len(rows),'errors':sum('error' in r for r in rows)},indent=2))
