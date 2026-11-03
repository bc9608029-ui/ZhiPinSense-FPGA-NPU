from pathlib import Path
r=Path('/root/rml24_three_modes_execution_20261029');p=r/'pagination_fixture.txt';assert not p.exists();lines=['RML24_HISTORY_V1']
for i in range(10):lines.append('%d %d %d %d 2 3 0.8 4 0.15 0 0.05'%(1700000000+i,1700000100+i,2404000000-i*1000000,i+1))
p.write_text('\n'.join(lines)+'\n')
s=(r/'retry_quiet_modes.py').read_text();old="[('FIXED','quiet_fixed02'),('BAND_SCAN','quiet_lock02'),('CONTINUOUS_SCAN','quiet_sweep02')]";assert s.count(old)==1;s=s.replace(old,"[('FIXED','pagination_ui01')]").replace("'--duration-sec','60'","'--duration-sec','900'").replace('candidate_history.txt','pagination_fixture.txt').replace('QUIET_RESULTS.json','PAGINATION_RESULTS.json').replace('delivery/scripts/run_candidate_eof_compat.py','delivery_progressfix1/scripts/run_candidate_eof_compat.py');(r/'run_pagination_ui.py').write_text(s);print('ISOLATED_TEN_ROW_FIXTURE_READY')
