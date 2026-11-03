import base64,gzip,json,re
from pathlib import Path
r=Path('/root/rml24_three_modes_execution_20261029');out={}
for name in ['formal_fixed01','formal_lock01','formal_sweep24_01']:
 p=r/name
 if not (p/'capture/final.json').exists() or not (p/'supervisor.json').exists():continue
 rows=[]
 for line in (p/'capture/records.jsonl').read_text().splitlines():
  v=json.loads(line);a=v['candidate'];rows.append(dict(frame_id=v['frame_id'],capture_time_ns=v['capture_time_ns'],pred=a['pred'],finite=a['finite'],center_hz=v['center_hz'],actual_lo_hz=v['actual_lo_hz'],error=a.get('error'),repeat_average=a.get('repeat_average'),scan_steps=v['scan_steps']))
 out[name]=dict(rows=rows,final=json.loads((p/'capture/final.json').read_text()),supervisor=json.loads((p/'supervisor.json').read_text()),npu_stop=re.findall(r'NPU_STREAM_STOP[^\r\n]*',(p/'npu.log').read_text(errors='replace')))
print('EVIDENCE_BEGIN');print(base64.b64encode(gzip.compress(json.dumps(out).encode())).decode());print('EVIDENCE_END')
