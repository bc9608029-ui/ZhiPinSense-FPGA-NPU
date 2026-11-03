import base64,gzip,json
from pathlib import Path
r=Path('/root/rml24_mainchain_diagnostic_20261028')
obj=dict(results=json.loads((r/'mean_replay01/results.json').read_text()),
         npu_stop=[v for v in (r/'mean_replay01/npu.log').read_text(errors='replace').splitlines() if 'NPU_STREAM_STOP' in v])
print('EVIDENCE_BEGIN')
print(base64.b64encode(gzip.compress(json.dumps(obj).encode())).decode())
print('EVIDENCE_END')
