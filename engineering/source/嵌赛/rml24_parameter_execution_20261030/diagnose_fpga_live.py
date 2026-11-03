import importlib.util,json,shlex,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('diag_helpers',ROOT/'run_tests.py');h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
old=Path(json.loads((ROOT/'MANUAL_FPGA_CURRENT.json').read_text())['root']);base=json.loads((old/'remote_root.json').read_text())['root']
out=old/'diagnostic';out.mkdir(exist_ok=True)
info=json.loads((old/'board_preflight.json').read_text());remote='/root/rml24_fpga_diag_'+str(int(time.time()))
h.remote('mkdir '+shlex.quote(remote))
for name in ['scan_xrt.cpp','scan_protocol.hpp','test_protocol.cpp','build_board.sh']:h.push(h.PREP/'fpga'/name,remote+'/'+name)
h.remote('bash '+shlex.quote(remote+'/build_board.sh'),log=out/'build.log',timeout=600)
h.remote(shlex.join([remote+'/scan_xrt','--probe']),log=out/'held_status.log',timeout=45)
print((out/'held_status.log').read_text(),flush=True)
for i,name in enumerate(['impulse','plus37','impulse','random','impulse']):
 dest=base+'/diag_'+str(i)
 r=h.remote(shlex.join([info['python'],'-I',info['root']+'/fpga/same_iq.py','--iq',base+'/vectors/'+name+'.i16',
                       '--out',dest,'--backend','fpga','--driver',remote+'/scan_xrt']),log=out/('trial_'+str(i)+'.log'),check=False,timeout=90)
 h.pull(dest+'/driver.log',out/('driver_'+str(i)+'.log'))
 h.pull(dest+'/result.json',out/('result_'+str(i)+'.json'))
 print(name,'rc='+str(r.returncode),(out/('driver_'+str(i)+'.log')).read_text()[-450:],flush=True)
h.write(out/'driver_identity.json',dict(root=remote,original_bitstream_unchanged=True))
