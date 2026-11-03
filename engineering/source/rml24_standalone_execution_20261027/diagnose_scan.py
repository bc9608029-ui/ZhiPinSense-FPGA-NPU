import json
from pathlib import Path
r=Path('/root/rml24_standalone_execution_20261027/smoke_scan01/capture/records.jsonl')
for line in r.read_text().splitlines():
    v=json.loads(line)
    print(json.dumps(dict(frame_id=v['frame_id'],elapsed_ms=round(v['elapsed_ms']),
               pred=v['candidate']['pred'],error=v['candidate'].get('error'),
               scan_steps=v['scan_steps'])))
