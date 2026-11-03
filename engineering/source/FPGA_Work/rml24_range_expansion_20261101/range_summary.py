from pathlib import Path
import json,collections
m=json.loads(Path('/root/rml24_range_expansion_20261101/mark.json').read_text());rows=[json.loads(x) for x in (Path(m['run'])/'capture/records.jsonl').read_text().splitlines()[m['first']:]];v=[x for x in rows if x['candidate'].get('finite')];print(json.dumps(dict(hz=m['hz'],records=len(rows),valid=len(v),preds=dict(collections.Counter(str(x['candidate']['pred']) for x in v)),actual_lo_hz=sorted(set(x['actual_lo_hz'] for x in rows)))))
