from pathlib import Path
import subprocess,time,json,re,base64,gzip,sys
p=Path(__file__).parent
serial='E:/scan_exec_20261027/serial.ps1'
def ps(args):
 r=subprocess.run(['powershell','-NoProfile','-File']+args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);v=r.stdout.decode('utf8',errors='replace');assert r.returncode==0,v;return v
def board(c):return ps([serial,'-Command',c,'-Seconds','3'])
def sync(name):
 text=ps(['E:/FPGA_Work/rml24_timing_fix_20261031/clock_sync_monotonic.ps1']);d=json.loads(text);(p/name).write_text(json.dumps(d,indent=2));return d
try:
 for mode in ['gainfreeze']:
  folder=p/mode;folder.mkdir(exist_ok=True);pre=sync(mode+'_CLOCK_PRE.json')
  (folder/'START.txt').write_text(board('nohup python3 /root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031/run_paired.py '+mode+' > /root/rml24_paired_'+mode+'.log 2>&1 < /dev/null &'))
  (p/'STATUS.json').write_text(json.dumps(dict(stage='RF_RUNNING',mode=mode)))
  subprocess.run([sys.executable,str(p/'tx_paired.py'),mode],check=True,stdout=(folder/'TX.log').open('w'),stderr=subprocess.STDOUT)
  sync(mode+'_CLOCK_POST.json')
  for _ in range(20):
   text=board('test -f /root/rml24_reduced_repeat_followup_20261101/'+mode+'/CAPTURE_RESULT.json && echo CAPTURE_FINISHED')
   if 'CAPTURE_FINISHED' in text.splitlines():break
   time.sleep(5)
  assert 'CAPTURE_FINISHED' in text.splitlines();time.sleep(5)
 (p/'START_CLASSIFY.txt').write_text(board('nohup /root/miniconda3/envs/torch_v2.0.1_aarch64/bin/python3 /root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031/classify_paired.py > /root/rml24_paired_classify.log 2>&1 < /dev/null &'))
 (p/'STATUS.json').write_text(json.dumps(dict(stage='RF_COMPLETE_CLASSIFICATION_STARTED',denominator=48)))
except Exception as e:
 (p/'STATUS.json').write_text(json.dumps(dict(stage='FAILED',error=str(e))));raise
