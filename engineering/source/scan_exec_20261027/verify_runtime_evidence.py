import pathlib,tarfile,json,re,hashlib
p=pathlib.Path(__file__).parent;checks={}
with tarfile.open(p/'board_runtime_evidence.tar.gz') as t:
 names=t.getnames();restores={n:json.loads(t.extractfile(n).read()) for n in names if n.endswith('/restore.json')};assert all(v==[] for v in restores.values())
 checks['restore_files_all_empty']=len(restores)
 for run,n in [('scan_narrow_r1',1920),('scan_wide_r1',1920),('centered_wide_v2',1920),('centered_narrow_v2',1920),('challenge78',576),('challenge78_v2',576),('mode_control_test',192)]:
  log=t.extractfile(run+'.log').read().decode(errors='replace');assert 'RML24_DUALMODE_RUN result=PASS' in log;assert f'NPU_STREAM_STOP frames={n} apply=1 reset={n-1} discipline=1' in log,run;checks[run]='PASS'
 ui=t.extractfile('ui_fourpage_waterfall.log').read().decode(errors='replace');assert 'TOUCH_CONTROL_RESULT result=PASS commands_sent=6 commands_applied=6 commands_rejected=0 commands_timeout=0 duplicate_commands=0' in ui
 restore=t.extractfile('final_restored_services.txt').read().decode();assert '6ee4461dfae6f1b513e1ae136dc489982ab95318e6aa3b8213654a17e2b8e00e' in restore;assert 'febdfe0940585b56d6725f04fdcad1a8a71b9fd703a3a4bc5fc6493b34229c7e' in restore;assert 'e0aa12029e9c5aa670a9340d9c078814b10dcfb0ee82c580adaad4f55affcf3a' in restore
 checks['physical_ui_touch_log']='PASS';checks['original_services_and_frozen_recovery']='PASS'
checks['evidence_sha256']=hashlib.sha256((p/'board_runtime_evidence.tar.gz').read_bytes()).hexdigest();(p/'board_evidence_independent_audit.json').write_text(json.dumps(checks,indent=2));print(json.dumps(checks))