import json
from pathlib import Path
r=Path(r'E:\rml24_gapfix_execution_20261028');d=json.loads((r.parent/'rml24_mainchain_diagnostic_20261028/IQ_DIAGNOSTIC.json').read_text(encoding='utf-8'))
(r/'offline_development_labels.json').write_text(json.dumps([dict(frame_id=v['frame_id'],label=v['label'],event_index=v['event_index']) for v in d['rows'] if v['event_index'] is not None]))
