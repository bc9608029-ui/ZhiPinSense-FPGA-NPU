import json
from pathlib import Path
p=Path('/root/rml24_standalone_execution_20261027/formal_fixed01/capture/records.jsonl')
rows=[json.loads(line) for line in p.read_text().splitlines()]
valid=[r for r in rows if r['candidate']['finite']]
cfos=sorted(r['candidate']['cfo_hz'] for r in valid)
print('CFO_HZ_RANGE',cfos[0],cfos[len(cfos)//2],cfos[-1])
for r in valid[::250]:
    c=r['candidate']
    print(json.dumps(dict(frame_id=r['frame_id'],pred=c['pred'],cfo_hz=c['cfo_hz'],
                         gain=c['gain'],dc=c['dc'],head=c['head_reference_relative_error'],
                         tail=c['tail_reference_relative_error'])))
