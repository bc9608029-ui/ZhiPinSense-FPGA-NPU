import json,gzip,base64,re
from pathlib import Path
r=Path('/root/rml24_three_modes_execution_20261029');run=r/'multifreq_sweep01';rows=[]
for line in (run/'capture/records.jsonl').read_text().splitlines():
 v=json.loads(line);a=v['candidate'];rows.append(dict(frame_id=v['frame_id'],capture_time_ns=v['capture_time_ns'],board_monotonic=v['board_monotonic'],center_hz=v['center_hz'],actual_lo_hz=v['actual_lo_hz'],finite=a.get('finite'),pred=a.get('pred'),error=a.get('error'),repeat_average=a.get('repeat_average'),input_sha256=a.get('input_sha256'),scan_steps=v['scan_steps'],elapsed_ms=v['elapsed_ms']))
obj=dict(rows=rows,history=(r/'multifreq_history.txt').read_text() if (r/'multifreq_history.txt').exists() else None)
for name,p in [('final',run/'capture/final.json'),('supervisor',run/'supervisor.json')]:obj[name]=json.loads(p.read_text()) if p.exists() else None
obj['npu_stop']=re.findall(r'NPU_STREAM_STOP[^\r\n]*',(run/'npu.log').read_text(errors='replace'))
print('EVIDENCE_BEGIN');print(base64.b64encode(gzip.compress(json.dumps(obj).encode())).decode());print('EVIDENCE_END')
