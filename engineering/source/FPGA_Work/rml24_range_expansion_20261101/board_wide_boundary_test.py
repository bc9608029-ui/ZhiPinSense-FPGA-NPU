from pathlib import Path
import socket,json,time,traceback
import subprocess
pid=int(subprocess.check_output(['systemctl','show','rml24-range-test','-p','MainPID','--value']).strip());args=Path('/proc/%d/cmdline'%pid).read_bytes().decode().strip('\0').split('\0');r=Path(args[args.index('--run')+1]);out=[]
def cmd(c):
 s=socket.socket(socket.AF_UNIX);s.settimeout(45);s.connect(str(r/'control.sock'));f=s.makefile('rwb');f.write((c+'\n').encode());f.flush();lines=[]
 while True:
  line=f.readline().decode().strip();lines.append(line)
  if 'accepted' not in line:break
 s.close();out.append(dict(command=c,replies=lines));return lines[-1]
def state():
 t=cmd('GET_TUNING');assert t.startswith('OK'),t
 return dict(x.split('=',1) for x in t.split() if '=' in x)
def ok(c):
 t=cmd(c);assert t.startswith('OK'),t;return t
try:
 ok('STOP');ok('SET_MODE FIXED')
 for hz in (70000000,325000000,3800000000,6000000000,2400000000):
  ok('SET_FIXED_HZ '+str(hz));d=state();assert int(d['fixed_hz'])==hz and int(d['fixed_readback_hz'])==hz
 for a,b,c,n in [(70000000,80000000,1000000,11),(5990000000,6000000000,1000000,11),(2395000000,2405000000,1000000,11),(2396000000,2404000000,2000000,5),(2395000000,2405000000,500000,21),(2395000000,2405000000,1500000,8)]:
  t=ok('SET_SCAN_RANGE_HZ %d %d %d'%(a,b,c));assert 'scan_points='+str(n) in t,t
  d=state();assert [int(d[k]) for k in ('start_hz','stop_hz','step_hz')]==[a,b,c]
 for c in ('2405000000 2395000000 1000000','2395000000 2395000000 1000000','2395000000 2405000000 0','2395000000 2405000000 -1','2395000000 2405000000 2304001','2395000000 2405000000 1'):
  before=state();assert cmd('SET_SCAN_RANGE_HZ '+c).startswith('ERR');after=state();assert all(before[k]==after[k] for k in ('start_hz','stop_hz','step_hz'))
 for mode in ('BAND_SCAN','CONTINUOUS_SCAN','FIXED'):
  ok('SET_MODE '+mode);ok('START');time.sleep(3);assert state()['mode']==mode;ok('STOP');assert state()['running']=='0'
 for hz in (69999999,6000000001):
  before=state();assert cmd('SET_FIXED_HZ '+str(hz)).startswith('ERR');after=state();assert before['fixed_hz']==after['fixed_hz']
 result=dict(passed=True)
except Exception:result=dict(passed=False,error=traceback.format_exc())
finally:
 try:
  ok('STOP');ok('SET_MODE FIXED');ok('SET_FIXED_HZ 2400000000');ok('SET_SCAN_RANGE_HZ 2395000000 2405000000 1000000');ok('START');result['restored']=state()
 except Exception:result['restore_error']=traceback.format_exc()
 result['steps']=out;(r/'POSTDEPLOY_PARAMETER_TEST.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
