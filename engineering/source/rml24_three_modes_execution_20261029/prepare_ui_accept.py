from pathlib import Path
r=Path('/root/rml24_three_modes_execution_20261029');p=r/'retry_quiet_modes.py';s=p.read_text();old="[('FIXED','quiet_fixed02'),('BAND_SCAN','quiet_lock02'),('CONTINUOUS_SCAN','quiet_sweep02')]";assert s.count(old)==1
s=s.replace(old,"[('FIXED','ui_accept01')]").replace("'--duration-sec','60'","'--duration-sec','900'").replace('candidate_history.txt','signal_history.txt').replace('QUIET_RESULTS.json','UI_ACCEPT_RESULTS.json')
(r/'run_ui_accept.py').write_text(s);print('UI_ACCEPT_RUNNER_READY')
