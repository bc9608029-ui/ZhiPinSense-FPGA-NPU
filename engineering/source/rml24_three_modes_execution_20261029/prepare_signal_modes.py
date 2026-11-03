from pathlib import Path
import json
r=Path('/root/rml24_three_modes_execution_20261029');s=(r/'retry_quiet_modes.py').read_text().replace('quiet_fixed02','signal_fixed01').replace('quiet_lock02','signal_lock01').replace('quiet_sweep02','signal_sweep01').replace("'--duration-sec','60'","'--duration-sec','90'").replace('candidate_history.txt','signal_history.txt').replace('QUIET_RESULTS.json','SIGNAL_RESULTS.json')
(r/'run_signal_modes.py').write_text(s)
print('SIGNAL_MODES_READY')
