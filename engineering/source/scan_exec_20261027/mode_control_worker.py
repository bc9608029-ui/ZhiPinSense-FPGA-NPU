import pathlib,json,socket,time
root=pathlib.Path('/root/rml24_scan_execution_20261027');p=root/'mode_control_test/capture/results.json';events=[]
def count():
 try:return len(json.loads(p.read_text())['records'])
 except (OSError,ValueError):return 0
def wait_count(n,timeout=100):
 end=time.monotonic()+timeout
 while count()<n:
  if time.monotonic()>end:raise TimeoutError(str(n))
  time.sleep(.05)
def cmd(line,n=2):
 stream.write((line+'\n').encode());reply=[stream.readline().decode().strip() for _ in range(n)];events.append({'command':line,'reply':reply,'frames':count(),'time':time.monotonic()});return reply
try:
 wait_count(4);s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);s.settimeout(5);s.connect('/run/rml24_diag_mode.sock');stream=s.makefile('rwb',buffering=0)
 cmd('STATUS',1);cmd('STOP');time.sleep(2);a=count();time.sleep(1);b=count();events.append({'stop_count_a':a,'stop_count_b':b,'stopped_stable':a==b});cmd('START');cmd('SET_MODE BAND_SCAN');wait_count(12);cmd('SET_MODE FIXED');wait_count(20);cmd('SET_MODE AUTO_LOCK',1);cmd('STATUS',1);stream.close();s.close()
 (root/'mode_control_protocol.json').write_text(json.dumps({'events':events},indent=2));print('MODE_PROTOCOL_TEST_COMPLETE')
except Exception as e:
 (root/'mode_control_protocol.json').write_text(json.dumps({'events':events,'error':repr(e)},indent=2));raise