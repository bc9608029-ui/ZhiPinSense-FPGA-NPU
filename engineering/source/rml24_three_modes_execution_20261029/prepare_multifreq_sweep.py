from pathlib import Path
r=Path('/root/rml24_three_modes_execution_20261029');s=(r/'retry_quiet_modes.py').read_text();old="[('FIXED','quiet_fixed02'),('BAND_SCAN','quiet_lock02'),('CONTINUOUS_SCAN','quiet_sweep02')]";assert s.count(old)==1
s=s.replace(old,"[('CONTINUOUS_SCAN','multifreq_sweep01')]").replace("'--duration-sec','60'","'--duration-sec','430'").replace('candidate_history.txt','multifreq_history.txt').replace('QUIET_RESULTS.json','MULTIFREQ_SWEEP_RESULTS.json').replace('delivery/scripts/run_candidate_eof_compat.py','delivery_progressfix1/scripts/run_candidate_eof_compat.py')
(r/'run_multifreq_sweep.py').write_text(s);print('MULTIFREQ_SWEEP_PREPARED')
