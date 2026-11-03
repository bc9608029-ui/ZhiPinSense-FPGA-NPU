import importlib.util,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('inspect_helpers',ROOT/'run_tests.py');h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
out=Path(json.loads((ROOT/'MANUAL_FPGA_CURRENT.json').read_text())['root'])
base=json.loads((out/'remote_root.json').read_text())['root']
for name in ['summary.json','7/result.json','7/driver.log','7/fpga.json','7/fpga.u64','7/software.u64']:
 p=out/'retrieved'/name;p.parent.mkdir(parents=True,exist_ok=True);h.pull(base+'/fpga/'+name,p)
print((out/'retrieved/7/result.json').read_text())
print((out/'retrieved/7/driver.log').read_text())
print((out/'retrieved/7/fpga.json').read_text())
