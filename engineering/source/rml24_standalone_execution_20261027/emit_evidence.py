"""Read-only serial export of this round's test evidence, no model payloads."""
import base64,gzip,json,hashlib
from pathlib import Path
r=Path('/root/rml24_standalone_execution_20261027')
result={}
for run in ['negative01','control01','smoke_fixed01','smoke_scan01','smoke_scan02','formal_fixed01','formal_scan01']:
    d=r/run/'capture'
    if not d.exists():continue
    rows=[]
    for line in (d/'records.jsonl').read_text().splitlines() if (d/'records.jsonl').exists() else []:
        v=json.loads(line);c=v['candidate']
        rows.append(dict(frame_id=v['frame_id'],capture_time_ns=v['capture_time_ns'],
                    board_monotonic=v['board_monotonic'],center_hz=v['center_hz'],
                    actual_lo_hz=v['actual_lo_hz'],pred=c['pred'],finite=c['finite'],
                    error=c.get('error'),input_sha256=c.get('input_sha256')))
    result[run]=dict(records=rows)
    for f in ['status.json','final.json','restore.json']:
        if (d/f).exists():result[run][f]=json.loads((d/f).read_text())
    log=r/(run+'.log')
    if log.exists():result[run]['log_tail']=log.read_text(errors='replace').splitlines()[-5:]
for f in ['control_test.json','ui_build.log','baseline_restoration.json']:
    if (r/f).exists():result[f]=(r/f).read_text()
if (r/'ui_live.log').exists():
    lines=(r/'ui_live.log').read_text(errors='replace').splitlines()
    result['ui_log_tail']=lines[-30:]
    result['ui_ready']=[x for x in lines if 'UI_LIVE_READY' in x or 'UI_TOUCH status' in x]
files=[r/'candidate/bin/board_ui_live_rml24_final',
       r/'candidate/rml24_final/board_runtime/standalone_receiver.py',
       r/'candidate/rml24_final/runtime/standalone_control.py',
       r/'candidate/rml24_final/runtime/receiver_core.py',
       r/'candidate/rml24_final/recovery/candidate_two_dc.py',
       Path('/etc/systemd/system/rml24-ui.service'),Path('/etc/systemd/system/rml24-receiver.service'),
       Path('/opt/rml24-system/bin/board_ui_live_rml24_final')]
model=Path('/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16')
files.extend([model/'rml24_adamrv11_bf16.json',model/'rml24_adamrv11_bf16.raw'])
result['board_source_and_baseline_hashes']={}
for p in files:
    if p.exists():
        digest=hashlib.sha256()
        with p.open('rb') as f:
            for block in iter(lambda:f.read(1048576),b''):digest.update(block)
        result['board_source_and_baseline_hashes'][str(p)]=digest.hexdigest()
native=r/'candidate/bin/board_ui_live_rml24_final'
if native.exists():
    with native.open('rb') as f:header=f.read(20)
    result['ui_elf_machine']=int.from_bytes(header[18:20],'little')
probe=r/'clean_npu_probe'
if (probe/'results.json').exists():
    result['clean_npu_probe']=dict(results=json.loads((probe/'results.json').read_text()))
    if (probe/'npu.log').exists():
        result['clean_npu_probe']['npu_stop']=[line for line in (probe/'npu.log').read_text(errors='replace').splitlines()
                                             if 'NPU_STREAM_STOP' in line]
payload=gzip.compress(json.dumps(result).encode())
print('EVIDENCE_BEGIN')
print(base64.b64encode(payload).decode())
print('EVIDENCE_END')
