from pathlib import Path
import json,subprocess,base64,re,time
r=Path(__file__).parent;state=json.loads((r/'DEVICE_STATUS.json').read_text());assert state['stage']=='DEVICE_PHASE_ENDED_ORIGINAL_RESTORED'
assert not (r/'FAILURE.json').exists()
cases=json.loads((r/'GUI_CASES.json').read_text());assert len(cases)==3
for c in cases:assert c['result']['error'] is None and c['result']['restore_status']=='READBACK_RESTORE_OK' and all(x['ok'] for x in c['result']['restore_readback'])
remote=state['board_evidence'];code="from pathlib import Path;import json,base64,gzip;root=Path("+repr(remote)+");rows=[json.loads(x) for x in (root/'quiet/capture/records.jsonl').read_text().splitlines()];out=dict(summary=json.loads((root/'SUMMARY.json').read_text()),rows=[dict(frame_id=x['frame_id'],capture_time_ns=x['capture_time_ns'],pred=x['candidate']['pred'],finite=x['candidate']['finite'],center_hz=x['center_hz'],scan_steps=x['scan_steps']) for x in rows]);print('EVIDENCE_BEGIN');print(base64.b64encode(gzip.compress(json.dumps(out).encode())).decode());print('EVIDENCE_END')"
b=base64.b64encode(code.encode()).decode();cmd='python3 -c "import base64;exec(base64.b64decode(\''+b+'\'))"'
q=subprocess.run(['powershell','-NoProfile','-File','E:/scan_exec_20261027/serial.ps1','-Command',cmd,'-Seconds','10'],capture_output=True,timeout=30);q.check_returncode();text=q.stdout.decode(errors='replace');(r/'audit_serial.log').write_text(text);m=re.search(r'EVIDENCE_BEGIN\r?\n([A-Za-z0-9+/=\s]+)EVIDENCE_END',text);assert m
import gzip
raw=base64.b64decode(re.sub(r'\s','',m[1]));(r/'RX_EVIDENCE.json.gz').write_bytes(raw);v=json.loads(gzip.decompress(raw));assert v['summary']['rc']==0 and v['summary']['supervisor']['clean_stop']
clock=json.loads((r/'clock_pre.json').read_text());assert clock['uncertainty_ms']<=250;offset=int(clock['offset_ns']);results=[]
for c in cases:
 eligible=[x for x in v['rows'] if c['tx_start_pc_ns']+1500000000<=x['capture_time_ns']+offset<=c['stop_request_pc_ns']-300000000 and x['scan_steps'] and abs(float(x['scan_steps'][0]['lo_hz'])-c['config']['center_hz'])<=1152000];x=eligible[0] if eligible else None
 results.append(dict(index=c['index'],config=c['config'],chosen_frame=x,correct=bool(x and x['finite'] and x['pred']==3 and abs(x['center_hz']-c['config']['center_hz'])<=10000),missing=x is None,source_sha=c['source_sha']))
out=dict(kind='THREE_FREQUENCY_GUI_SWEEP_FUNCTIONAL_NOT_FORMAL_ACCURACY',denominator=3,correct=sum(x['correct'] for x in results),missing=sum(x['missing'] for x in results),clock_uncertainty_ms=clock['uncertainty_ms'],gui_start_stop_and_restore_pass=True,receiver_summary=v['summary'],results=results)
(r/'GUI_FREQUENCY_RESULT.json').write_text(json.dumps(out,indent=2));print(json.dumps({k:x for k,x in out.items() if k not in ['receiver_summary','results']}))
