import sys,time,socket,json,subprocess,copy
from pathlib import Path
r=Path('/root/rml24_stage7_execution_20261027');sys.path.insert(0,str(r/'final_waterfall_fix1/rml24_final/runtime'));from ui_event import build_board_ui_result
sock='/tmp/stage7_waterfall_fix1_test.sock';log=r/'waterfall_fix1_process_test.log';events=[json.loads(x) for x in (Path('/root/rml24_stage7_post_jtag_r1_20261027/capture/ui_events.jsonl')).read_text().splitlines()];good=[build_board_ui_result(e) for e in events[:3]];assert all(good)
f=log.open('w');p=subprocess.Popen([str(r/'final_waterfall_fix1/bin/board_ui_live_rml24_final'),'--headless','--no-touch','--sock='+sock,'--ctl-sock=/tmp/stage7_waterfall_fix1_control_test.sock'],stdout=f,stderr=subprocess.STDOUT)
def send(c,x):c.sendall((json.dumps(x)+'\n').encode());time.sleep(.18)
try:
 for _ in range(100):
  if Path(sock).exists():break
  assert p.poll() is None
  time.sleep(.05)
 c=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);c.connect(sock);send(c,good[0]);send(c,good[1]);send(c,good[1]);bad=copy.deepcopy(good[2]);bad['measurements']['spectrum_dbfs_x4']=bad['measurements']['spectrum_dbfs_x4'][:-1];send(c,bad);c.close();time.sleep(.25)
 c=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);c.connect(sock);send(c,good[0]);c.close();time.sleep(.25)
finally:
 p.terminate();p.wait(timeout=10);f.close()
s=log.read_text();checks=dict(process_exit_zero=p.returncode==0,two_stream_resets=s.count('UI_WATERFALL_RESET reason=producer_connected rows=0')==2,first_row_per_stream=s.count('UI_WATERFALL_ROW frame=0 rows=1')==2,history_advances='UI_WATERFALL_ROW frame=1 rows=2' in s,duplicate_does_not_advance=s.count('UI_WATERFALL_ROW')==3,malformed_rejected='received=5 valid=4 rejected=1' in s);(r/'waterfall_fix1_process_test.json').write_text(json.dumps(checks,indent=2));print(json.dumps(checks),flush=True);assert all(checks.values())