from pathlib import Path
from types import SimpleNamespace as D
import json
from continuous_sweep_contract import ContinuousSweep
class LO:
 def tune(self,hz):return hz
 def flush(self):pass
rows=[]
def case(discovery,confirmation,expect,expected_callback):
 calls=[];s=ContinuousSweep();r=s.probe([2403000000],LO(),lambda:object(),lambda raw:discovery,lambda:None,2395000000,2405000000,centred_detect=lambda raw:(calls.append(1) or confirmation));assert bool(r[3]['accepted'])==expect;assert len(calls)==expected_callback;return r[3]
rows.append(case(D(score=.8,coarse_cfo_hz=600000),D(score=.9,coarse_cfo_hz=10),True,1))
rows.append(case(D(score=.05,coarse_cfo_hz=0),D(score=.9,coarse_cfo_hz=0),False,0))
rows.append(case(D(score=.8,coarse_cfo_hz=600000),D(score=.9,coarse_cfo_hz=2000),False,1))
rows.append(case(D(score=.8,coarse_cfo_hz=600000),D(score=.09,coarse_cfo_hz=0),False,1))
Path(__file__).with_name('CENTER_BRANCH_CONTRACT.json').write_text(json.dumps(dict(scope='Software branch/gate contract only, not RF',passed=4,rows=rows),indent=2));print('CENTRED_BRANCH_CONTRACT_PASS4')
