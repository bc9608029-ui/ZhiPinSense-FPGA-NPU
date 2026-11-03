#!/usr/bin/env python3
"""Fail closed across worker/supervisor restarts; no automatic hardware reset."""
import argparse,fcntl,json,os,signal,subprocess,sys,time
from pathlib import Path
BLOCKED=78

def main():
 p=argparse.ArgumentParser();p.add_argument('--state-dir',type=Path,required=True);p.add_argument('command',nargs=argparse.REMAINDER);a=p.parse_args()
 if not a.command:raise ValueError('worker command required')
 a.state_dir.mkdir(parents=True,exist_ok=True)
 lock=(a.state_dir/'owner.lock').open('a')
 try:fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:print('HARDWARE_OWNER_ACTIVE',flush=True);return BLOCKED
 marker=a.state_dir/'reset_required.json'
 if marker.exists():print('HARDWARE_RESET_REQUIRED '+str(marker),flush=True);return BLOCKED
 # Create before any Device open, atomically and durably. SIGKILL retains it.
 payload=dict(pid=os.getpid(),time_ns=time.time_ns(),boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),command=a.command)
 fd=os.open(str(marker),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'w') as f:json.dump(payload,f);f.flush();os.fsync(f.fileno())
 d=os.open(str(a.state_dir),os.O_RDONLY);os.fsync(d);os.close(d)
 child=[None];pending=[False]
 def stop(*_):
  pending[0]=True
  if child[0] is not None and child[0].poll() is None:child[0].terminate()
 signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
 try:
  if pending[0]:return BLOCKED
  child[0]=subprocess.Popen(a.command,pass_fds=(lock.fileno(),))
  if pending[0] and child[0].poll() is None:child[0].terminate()
  rc=child[0].wait()
 except BaseException as exc:print('HARDWARE_GUARD_ERROR '+repr(exc),flush=True);return BLOCKED
 if rc!=0:print('HARDWARE_RESET_REQUIRED worker_rc='+str(rc),flush=True);return BLOCKED
 marker.unlink();print('HARDWARE_GUARD_CLEAN_EXIT',flush=True);return 0
if __name__=='__main__':sys.exit(main())
