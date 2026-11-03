import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import sys,json
from pathlib import Path
import numpy as np
p=Path('E:/FPGA_Work/rml24_rate_adaptation_research_20261101');sys.path.insert(0,str(p))
from rate_recovery import recover_rate_and_repeats
rng=np.random.default_rng(588021);rows=[]
for i in range(6):
 z=rng.normal(size=65536)+1j*rng.normal(size=65536);accepted=[]
 for estimate in range(-100,101,5):
  q=np.arange(len(z))/(1+estimate/1e6)
  corrected=np.interp(q,np.arange(len(z)),z.real)+1j*np.interp(q,np.arange(len(z)),z.imag)
  try:
   _,m=recover_rate_and_repeats(corrected);accepted.append(dict(estimate=estimate,meta=m))
  except RuntimeError:pass
 rows.append(dict(index=i,accepted=accepted));(p/'FINE_GRID_NOISE.json').write_text(json.dumps(dict(scope='PC synthetic only; expanded timing grid; not an operational false alarm rate',rows=rows),indent=2));print(i,len(accepted),flush=True)
