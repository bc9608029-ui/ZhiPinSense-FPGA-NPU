from pathlib import Path
import os,subprocess
r=Path(r'E:\rml24_fpga_aux_execution_20261028');template=Path(r'E:\rml24_fpga_execution_20261027\procise_project\run.tcl').read_text()
env=dict(os.environ);env.update(TCL_LIBRARY='D:/FMSH/Procise/tcl8.4',ICTIME_HOME='D:/FMSH/Procise',APP_DIR='D:/FMSH/Procise',FMSH_DB='D:/FMSH/Procise/db');env['PATH']='D:/FMSH/Procise/dll;D:/FMSH/Procise/bin;'+env['PATH']
for name in ['window_mul_q15','fft_magnitude_square_u52']:
 d=r/('procise_'+name);d.mkdir(exist_ok=False)
 (d/(name+'.v')).write_bytes((r/'source/rtl'/(name+'.sv')).read_bytes())
 s=template.replace('frame_statistics',name).replace('E:/rml24_fpga_execution_20261027/procise_rtl/'+name+'.v',(d/(name+'.v')).as_posix())
 (d/'run.tcl').write_text(s)
 with (d/'stdout.log').open('wb') as out,(d/'stderr.log').open('wb') as err:
  p=subprocess.run(['D:/FMSH/Procise/bin/procise.exe','-sh'],input=b'source run.tcl\n',cwd=str(d),env=env,stdout=out,stderr=err,timeout=600)
 print(name,p.returncode,flush=True)
