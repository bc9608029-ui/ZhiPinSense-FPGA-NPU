from pathlib import Path
import numpy as np,json
from precision_contract import choose_precision
p=Path(__file__).parent;assets=Path('E:/FPGA_Work/rml24_tx_console_integration_20261031/console/assets');rows=[]
for f in sorted(assets.glob('*.bin')):
 x=np.frombuffer(f.read_bytes(),'<f4')
 for gain in (-89,-80,-70,-60,-40,-20,0):
  r=choose_precision(x,gain);assert r['peak_component']<=.95*2047+1e-8;assert abs(r['ideal_pilot_mismatch_db'])<=.1250001;rows.append(dict(file=f.name,nominal_gain=gain,**r))
assert len(rows)==240*7
(p/'PRECISION_CONTRACT_1680.json').write_text(json.dumps(dict(scope='PC numerical constraints only; supplied conservative gain bounds, not queried hardware; no RF claim',cases=len(rows),max_ideal_mismatch_db=max(abs(x['ideal_pilot_mismatch_db']) for x in rows),max_component=max(x['peak_component'] for x in rows),min_scale=min(x['scale'] for x in rows),max_scale=max(x['scale'] for x in rows)),indent=2));print('NUMERICAL_CONTRACT_PASS',len(rows))
