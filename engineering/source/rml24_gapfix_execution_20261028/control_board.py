import os,subprocess,time,socket,json
from pathlib import Path
r=Path('/root/rml24_gapfix_execution_20261028');base=r/'candidate';results=[];rx=None;ui=None
sock='/run/rml24_gapfix_control.sock'
def command(s):
 c=socket.socket(socket.AF_UNIX);c.settimeout(35);c.connect(sock);c.sendall((s+'\n').encode());data=b''
 while b'\n' not in data:
  v=c.recv(4096)
  if not v:break
  data+=v
 c.close();v=data.decode();results.append({'command':s,'response':v});(r/'control_results.json').write_text(json.dumps(results,indent=2));return v
try:
 subprocess.run(['systemctl','stop','rml24-receiver','rml24-ui'],check=True)
 if subprocess.run(['pgrep','-x','npu_stream'],stdout=subprocess.DEVNULL).returncode==0:raise RuntimeError('NPU occupied')
 ui=subprocess.Popen([str(base/'bin/board_ui_live_rml24_final'),'--sock=/run/rml24_gapfix_ui.sock','--ctl-sock='+sock,'--control-timeout-ms=35000','--stats-interval=10','--run-id=gapfix_control'],stdout=(r/'control_ui.log').open('w'),stderr=subprocess.STDOUT)
 env=dict(os.environ,PATH='/root/miniconda3/envs/torch_v2.0.1_aarch64/bin:/usr/bin:/bin',USER_RF_VALIDATION_APPROVED='YES',DURATION_SEC='150',UI_SOCKET='/run/rml24_gapfix_ui.sock',UI_CONTROL_SOCKET=sock)
 rx=subprocess.Popen(['bash',str(base/'rml24_final/board_runtime/run_repeat_mean_gapfix1.sh'),'--run',str(r/'control_no_tx01'),'--legacy-root','/root/amr_rescue_20261025','--model-dir','/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16','--initial-mode','FIXED'],env=env,stdout=(r/'control_rx.log').open('w'),stderr=subprocess.STDOUT)
 for _ in range(50):
  if rx.poll() is not None:raise RuntimeError('RX startup failed')
  if 'STANDALONE_READY' in (r/'control_rx.log').read_text():break
  time.sleep(.5)
 else:raise RuntimeError('RX readiness timeout')
 for s in ['GET_TUNING','SET_MODE AUTO_LOCK','SET_FIXED_HZ 2299999999','SET_SCAN_RANGE_HZ 2405000000 2395000000 1000000','SET_SCAN_RANGE_HZ 2300000000 2500000000 1','SET_FIXED_HZ 2401000000','GET_TUNING','SET_SCAN_RANGE_HZ 2396000000 2404000000 2000000','GET_TUNING','STOP','START','SET_FIXED_HZ 2400000000','SET_SCAN_RANGE_HZ 2395000000 2405000000 1000000','GET_TUNING']:
  print(s,repr(command(s)),flush=True)
 print('CONTROL_SEQUENCE_COMPLETE',flush=True)
finally:
 if rx is not None and rx.poll() is None:
  for p in Path('/proc').glob('[0-9]*/cmdline'):
   try:
    args=p.read_bytes().split(b'\0')
    if str(base/'rml24_final/board_runtime/receiver_repeat_mean_gapfix1.py').encode() in args:os.kill(int(p.parent.name),15)
   except (FileNotFoundError,ProcessLookupError,PermissionError):pass
  try:rx.wait(timeout=30)
  except subprocess.TimeoutExpired:print('RX_CLEANUP_TIMEOUT',flush=True)
 if ui is not None:ui.terminate();ui.wait(timeout=10)
 if subprocess.run(['pgrep','-x','npu_stream'],stdout=subprocess.DEVNULL).returncode==0:raise RuntimeError('NPU still running, baseline restore withheld')
 subprocess.run(['systemctl','start','rml24-ui','rml24-receiver'],check=True)
 print('BASELINE_RESTORED',flush=True)
