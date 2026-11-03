import runpy,sys,numpy as np
from pathlib import Path
p=Path('E:/')/'\u5d4c\u8d5b'/'rml24_multifreq_tx_validation_20261029/scripts/verify_tx_offline.py'
if not hasattr(np,'trapezoid'):np.trapezoid=np.trapz
sys.path.insert(0,str(p.parent));sys.argv=[str(p)]+sys.argv[1:];print('OFFLINE_NUMPY_COMPAT trapezoid=trapz; original source unchanged',flush=True);runpy.run_path(str(p),run_name='__main__')

