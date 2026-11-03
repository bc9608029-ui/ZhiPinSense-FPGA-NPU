from pathlib import Path
import hashlib,json
r=Path('/root/rml24_three_modes_execution_20261029');p=r/'delivery_progressfix1/scripts/run_candidate_eof_compat.py';b=p.read_bytes();expected=json.loads((r/'SUPERVISOR_EOF_COMPAT.json').read_text());assert hashlib.sha256(b).hexdigest()==expected['compat_sha'];s=b.decode();assert s.count('rx.wait(timeout=1.0)')==1;s=s.replace('rx.wait(timeout=1.0)','rx.wait(timeout=40.0)').replace('import json\n','import json\nimport re\n',1)
old="                result['normal_npu_eof_before_rx_reap']=True";assert s.count(old)==1
new="""                final=json.loads((run/'capture/final.json').read_text())
                restored=json.loads((run/'capture/restore.json').read_text())
                accounting=re.search(r'NPU_STREAM_STOP frames=(\\d+) apply=(\\d+) reset=(\\d+) discipline=(\\d+)',(run/'npu.log').read_text(errors='replace'))
                if ui.poll() is not None:raise RuntimeError('UI exited during RX finalization')
                if restored or final['restore_errors']:raise RuntimeError('RX restore failed')
                frames=final['valid']*8
                if not accounting or tuple(map(int,accounting.groups()))!=(frames,1,max(0,frames-1),1):raise RuntimeError('NPU final accounting mismatch')
                result['normal_npu_eof_before_rx_reap']=True
                result['finalization_accounting_verified']=True"""
s=s.replace(old,new);q=p.with_name('run_candidate_finalize_v2.py');q.write_text(s);(r/'SUPERVISOR_FINALIZE_V2.json').write_text(json.dumps(dict(original_sha=hashlib.sha256(b).hexdigest(),new_sha=hashlib.sha256(q.read_bytes()).hexdigest(),max_finalization_wait_sec=40,original_preserved=True,model_rx_ui_unchanged=True),indent=2))
worker=(r/'retry_quiet_modes.py').read_text();needle="[('FIXED','quiet_fixed02'),('BAND_SCAN','quiet_lock02'),('CONTINUOUS_SCAN','quiet_sweep02')]";assert worker.count(needle)==1;worker=worker.replace(needle,"[('CONTINUOUS_SCAN','finalize_v2_quiet01')]").replace("'--duration-sec','60'","'--duration-sec','20'").replace('QUIET_RESULTS.json','FINALIZE_V2_SHORT_RESULTS.json').replace('candidate_history.txt','finalize_v2_history.txt').replace('delivery/scripts/run_candidate_eof_compat.py','delivery_progressfix1/scripts/run_candidate_finalize_v2.py');(r/'run_finalize_v2_short.py').write_text(worker);print('FINALIZE_V2_READY')
