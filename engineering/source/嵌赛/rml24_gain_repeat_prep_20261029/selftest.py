import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import tempfile
from pathlib import Path
from unittest.mock import patch
import numpy as np
from gain_control import configure
from capture_gain import capture
from repeat_ablation import average_first,validate_unaveraged_provenance

class Fake:
    rx='rx'
    def __init__(self):self.v=dict(gain_control_mode='manual',hardwaregain='30',sampling_frequency='2560000',rf_bandwidth='18000000');self.original=dict(self.v);self.closed=False
    def get(self,ch,k):return str(self.v[k])
    def set(self,ch,k,v):self.v[k]=str(v)
    def config_rx(self):self.v['hardwaregain']='35'
    def receive(self,n):return np.ones(n,dtype=np.complex64)
    def close(self):self.closed=True;self.v=dict(self.original);return []

with patch('gain_control.time.sleep'):
    r=Fake();assert configure(r,'manual',45)['gain_db']==45
    assert configure(r,'slow_attack',None)['mode']=='slow_attack'
    try:configure(r,'manual',100)
    except ValueError:pass
    else:raise AssertionError()
    with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as t:
        r=Fake();result=capture(r,Path(t)/'new','manual',35,2,0)
        assert result['raw_records']==2 and r.closed
        assert len(list((Path(t)/'new').glob('*.raw.npy')))==2
    r=Fake()
    def fail(n):raise RuntimeError('injected capture error')
    r.receive=fail
    with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as t:
        try:capture(r,Path(t)/'failed','slow_attack',None,1,0)
        except RuntimeError:pass
        else:raise AssertionError()
        assert r.closed and (Path(t)/'failed/capture_summary.json').exists()
x=np.random.default_rng(1).normal(size=(8,2,1024)).astype('<f4')
for n in (1,2,4,8):np.testing.assert_array_equal(average_first(x,n)[0],x[:n].mean(axis=0,dtype=np.float64).astype('<f4'))
try:validate_unaveraged_provenance({'repeat_average_applied':True})
except ValueError:pass
else:raise AssertionError()
print('PREP_SELFTEST PASS: simulated only, no SDR, no inference')
