import json,os,signal,subprocess,sys,tempfile,time
from pathlib import Path
root=Path(__file__).parent;guard=root/'hardware_restart_guard.py';results=[]
def run(state,code):return subprocess.run([sys.executable,str(guard),'--state-dir',str(state),sys.executable,'-c',code],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,universal_newlines=True)
with tempfile.TemporaryDirectory(prefix='rml24_guard_test_') as tmp:
 b=Path(tmp)
 s=b/'normal';a=run(s,'pass');assert a.returncode==0 and not (s/'reset_required.json').exists();assert run(s,'pass').returncode==0;results.append('normal exit permits next launch')
 s=b/'busy';a=run(s,'raise SystemExit(3)');assert a.returncode==78 and (s/'reset_required.json').exists();a=run(s,'raise Exception("MUST_NOT_RUN")');assert a.returncode==78 and 'MUST_NOT_RUN' not in a.stdout;results.append('unsafe rc3 blocks subsequent worker')
 s=b/'signal';a=run(s,'import os,signal;os.kill(os.getpid(),signal.SIGKILL)');assert a.returncode==78 and run(s,'pass').returncode==78;results.append('killed worker blocks restart')
 s=b/'missing';a=subprocess.run([sys.executable,str(guard),'--state-dir',str(s),'/nonexistent_rml24_worker'],stdout=subprocess.PIPE);assert a.returncode==78 and run(s,'pass').returncode==78;results.append('launch exception fails closed')
 s=b/'outer_kill';ready=b/'ready';cmd='from pathlib import Path;import time;Path('+repr(str(ready))+').write_text("ready");time.sleep(2)'
 p=subprocess.Popen([sys.executable,str(guard),'--state-dir',str(s),sys.executable,'-c',cmd],stdout=subprocess.DEVNULL)
 deadline=time.monotonic()+10
 while not ready.exists():
  assert time.monotonic()<deadline;time.sleep(.02)
 assert run(s,'pass').returncode==78;os.kill(p.pid,signal.SIGKILL);p.wait();assert run(s,'pass').returncode==78;time.sleep(2.2);assert run(s,'pass').returncode==78;results.append('supervisor kill and surviving child cannot bypass lock/marker')
 s=b/'stale';s.mkdir();(s/'reset_required.json').write_text('{broken');assert run(s,'pass').returncode==78;results.append('malformed marker fails closed')
print(json.dumps(dict(passed=len(results),tests=results),indent=2))
