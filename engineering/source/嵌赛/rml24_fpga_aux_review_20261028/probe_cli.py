from pathlib import Path
import subprocess,os
r=Path(r'E:\rml24_fpga_aux_execution_20261028');env=dict(os.environ);env.update(TCL_LIBRARY='D:/FMSH/Procise/tcl8.4',ICTIME_HOME='D:/FMSH/Procise',APP_DIR='D:/FMSH/Procise',FMSH_DB='D:/FMSH/Procise/db');env['PATH']='D:/FMSH/Procise/dll;D:/FMSH/Procise/bin;'+env['PATH']
(r/'probe.tcl').write_text('set f [open probe_pass.txt w]\nputs $f PROCISE_TCL_EXECUTED\nclose $f\nexit 0\n')
with (r/'probe_stdout.log').open('wb') as out:
 p=subprocess.Popen(['D:/FMSH/Procise/bin/procise.exe','-sh','-f','probe.tcl'],cwd=str(r),env=env,stdout=out,stderr=subprocess.STDOUT)
 try:print('EXIT',p.wait(timeout=20))
 except subprocess.TimeoutExpired:p.kill();p.wait();print('PROBE_TIMEOUT')
print('MARKER',(r/'probe_pass.txt').exists())
