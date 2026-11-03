from pathlib import Path
import json,subprocess,base64,re,time
r=Path(__file__).parent;state=json.loads((r/'DEVICE_STATUS.json').read_text());assert state['stage']=='DEVICE_PHASE_ENDED_ORIGINAL_RESTORED'
assert not (r/'FAILURE.json').exists()
cycle=json.loads((r/'GUI_CYCLE_RESULT.json').read_text());truth=json.loads((r/'TRUTH_MAPPING_PC_ONLY.json').read_text());assert len(truth)==24 and cycle['result']['restore_status']=='READBACK_RESTORE_OK';events=cycle['events'];tx=[x for x in events if x['event']=='transmitting'];muted={x['index']:x['time_ns'] for x in events if x['event']=='muted'};assert len(tx)==24;cases=[dict(index=i,tx_start_pc_ns=x['time_ns'],stop_request_pc_ns=muted[i],source_sha=x['source_sha256'],expected=truth[i]['class_index']) for i,x in enumerate(tx)];assert all(x['source_sha']==truth[x['index']]['source_sha'] for x in cases)
remote=state['board_evidence'];code="from pathlib import Path;import json,base64,gzip;root=Path("+repr(remote)+");rows=[json.loads(x) for x in (root/'quiet/capture/records.jsonl').read_text().splitlines()];out=dict(summary=json.loads((root/'SUMMARY.json').read_text()),rows=[dict(frame_id=x['frame_id'],capture_time_ns=x['capture_time_ns'],pred=x['candidate']['pred'],finite=x['candidate']['finite']) for x in rows]);print('EVIDENCE_BEGIN');print(base64.b64encode(gzip.compress(json.dumps(out).encode())).decode());print('EVIDENCE_END')"
b=base64.b64encode(code.encode()).decode();cmd='python3 -c "import base64;exec(base64.b64decode(\''+b+'\'))"'
q=subprocess.run(['powershell','-NoProfile','-File','E:/scan_exec_20261027/serial.ps1','-Command',cmd,'-Seconds','10'],capture_output=True,timeout=30);q.check_returncode();text=q.stdout.decode(errors='replace');(r/'audit_serial.log').write_text(text);m=re.search(r'EVIDENCE_BEGIN\r?\n([A-Za-z0-9+/=\s]+)EVIDENCE_END',text);assert m
import gzip
raw=base64.b64decode(re.sub(r'\s','',m[1]));(r/'RX_EVIDENCE.json.gz').write_bytes(raw);v=json.loads(gzip.decompress(raw));assert v['summary']['rc']==0 and v['summary']['supervisor']['clean_stop']
clock=json.loads((r/'clock_pre.json').read_text());assert clock['uncertainty_ms']<=250;offset=int(clock['offset_ns']);results=[]
for c in cases:
 eligible=[x for x in v['rows'] if c['tx_start_pc_ns']+1500000000<=x['capture_time_ns']+offset<=c['stop_request_pc_ns']-300000000];x=eligible[0] if eligible else None
 results.append(dict(index=c['index'],expected=c['expected'],chosen_frame=x,correct=bool(x and x['finite'] and x['pred']==c['expected']),missing=x is None,source_sha=c['source_sha']))
out=dict(kind='GUI_24CLASS_NEW_SEED_MESSAGE_1_RF_SMOKE_NOT_240_REGRESSION',denominator=24,correct=sum(x['correct'] for x in results),missing=sum(x['missing'] for x in results),clock_uncertainty_ms=clock['uncertainty_ms'],gui_start_stop_and_restore_pass=True,receiver_summary=v['summary'],results=results)
(r/'GUI_24_RF_RESULT.json').write_text(json.dumps(out,indent=2));print(json.dumps({k:x for k,x in out.items() if k not in ['receiver_summary','results']}))
