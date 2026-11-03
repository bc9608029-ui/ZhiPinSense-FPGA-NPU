import base64,gzip,hashlib,json
from pathlib import Path
r=Path('/root/rml24_repeat_mean_validation_20261028');e={}
for run in ['candidate_fixed01','candidate_fixed02','candidate_scan01']:
    d=r/run/'capture'
    if not (d/'final.json').exists():continue
    rows=[]
    for line in (d/'records.jsonl').read_text().splitlines():
        v=json.loads(line);c=v['candidate']
        rows.append(dict(frame_id=v['frame_id'],capture_time_ns=v['capture_time_ns'],
                    pred=c['pred'],finite=c['finite'],actual_lo_hz=v['actual_lo_hz'],
                    input_sha256=c.get('input_sha256'),error=c.get('error'),
                    repeat_average=c.get('repeat_average'),window_predictions=c.get('window_predictions')))
    e[run]=dict(records=rows,final=json.loads((d/'final.json').read_text()),
                log_tail=(r/(run+'.log')).read_text(errors='replace').splitlines()[-6:])
hashes={}
for p in [Path('/root/rml24_mainchain_diagnostic_20261028/repeat_mean_candidate.py'),
          Path('/root/rml24_mainchain_diagnostic_20261028/receiver_repeat_mean_v1.py'),
          Path('/root/rml24_standalone_execution_20261027/candidate/rml24_final/board_runtime/run_repeat_mean_v1.sh')]:
    hashes[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
e['source_hashes']=hashes
closure=r/'runtime_closure.json'
if closure.exists():e['runtime_closure']=json.loads(closure.read_text())
cleanup=r/'cleanup.json'
if cleanup.exists():e['cleanup']=json.loads(cleanup.read_text())
units={}
for name in ['rml24-ui.service','rml24-receiver.service']:
    p=Path('/etc/systemd/system')/name
    units[name]=hashlib.sha256(p.read_bytes()).hexdigest()
e['baseline_unit_hashes']=units
print('EVIDENCE_BEGIN');print(base64.b64encode(gzip.compress(json.dumps(e).encode())).decode());print('EVIDENCE_END')
