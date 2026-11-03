import importlib.util,json,tempfile,sys,subprocess,time
from pathlib import Path
from types import SimpleNamespace
root=Path('/root/rml24_fpga_ui_20261031/delivery_guard_persistent')
spec=importlib.util.spec_from_file_location('guard_supervisor',root/'scripts/run_candidate_finalize_v2.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
realrun=subprocess.run;realpopen=subprocess.Popen
class Blocked:
 def __init__(self,args,**kw):self.args=args;self.pid=999999;self.returncode=78
 def poll(self):return 78
 def terminate(self):raise AssertionError('must not terminate exited child')
m.preflight=lambda a:None
m.subprocess.Popen=Blocked
m.subprocess.run=lambda args,**kw:SimpleNamespace(returncode=3) if args[0]=='systemctl' else (_ for _ in ()).throw(AssertionError('unexpected hardware action'))
m.wait_ready=lambda *args,**kw:(_ for _ in ()).throw(RuntimeError('simulated guard block before hardware open'))
with tempfile.TemporaryDirectory(prefix='guard_supervisor_') as tmp:
 run=Path(tmp)/'run';sys.argv=['test','--legacy-root','/tmp','--model-dir','/tmp','--npu-sha','0'*64,'--run',str(run)]
 rc=m.main();v=json.loads((run/'supervisor.json').read_text());assert rc==78 and v['hardware_reset_required'] and not v['clean_stop'];print('SUPERVISOR_PROPAGATES_78 PASS')
# Restore monkeypatches before independent real systemd transient mock test.
subprocess.run=realrun;subprocess.Popen=realpopen
unit='rml24-guard-mock-'+str(int(time.time()))
q=realrun(['systemd-run','--unit='+unit,'--property=Restart=on-failure','--property=RestartPreventExitStatus=78','/bin/sh','-c','exit 78'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT);assert q.returncode==0,q.stdout
try:
 time.sleep(2)
 q=realrun(['systemctl','show',unit,'-p','NRestarts','-p','ExecMainStatus'],stdout=subprocess.PIPE,universal_newlines=True);values=dict(x.split('=',1) for x in q.stdout.splitlines());assert values['NRestarts']=='0' and values['ExecMainStatus']=='78',values;print('SYSTEMD_PREVENTS_RESTART_78 PASS '+str(values))
finally:realrun(['systemctl','reset-failed',unit],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
