"""Detached supervision of the running parameter task and subsequent FPGA trial."""
import ctypes,datetime,json,os,subprocess,sys,time,traceback
from pathlib import Path
HERE=Path(__file__).resolve().parent
def state(stage,**v):
 p=HERE/'SUPERVISOR_STATUS.json';tmp=p.with_suffix('.tmp')
 tmp.write_text(json.dumps(dict(stage=stage,time=datetime.datetime.now().astimezone().isoformat(),pid=os.getpid(),**v),indent=2),encoding='utf8');os.replace(tmp,p)
def read(p):return json.loads(p.read_text(encoding='utf8'))
def main():
 stage=read(HERE/'STATUS.json');pid=stage['pid']
 k=ctypes.WinDLL('kernel32',use_last_error=True)
 k.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong];k.OpenProcess.restype=ctypes.c_void_p
 k.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong];k.WaitForSingleObject.restype=ctypes.c_ulong
 k.CloseHandle.argtypes=[ctypes.c_void_p]
 handle=k.OpenProcess(0x100000,False,pid)
 if handle:
  try:
   while k.WaitForSingleObject(handle,15000)==258:
    state('SUPERVISING_PARAMETER_TASK',parameter_pid=pid,parameter_status=read(HERE/'STATUS.json'))
  finally:k.CloseHandle(handle)
 stage=read(HERE/'STATUS.json')
 if stage['stage']!='PARAMETER_TESTS_COMPLETE':
  state('PARAMETER_FAILURE_REQUIRES_EVIDENCE_REVIEW',parameter_status=stage)
  return 1
 state('STARTING_FPGA_ISOLATED_TESTS')
 env=dict(os.environ,PYTHONIOENCODING='utf8',PYTHONDONTWRITEBYTECODE='1')
 with (HERE/'fpga_supervised.log').open('w',encoding='utf8') as f:
  p=subprocess.run([sys.executable,'-I',str(HERE/'run_fpga_tests.py')],stdout=f,stderr=subprocess.STDOUT,env=env)
 state('ALL_EXECUTION_STAGES_ENDED',fpga_rc=p.returncode,production_promoted=False)
 return p.returncode
if __name__=='__main__':
 try:raise SystemExit(main())
 except Exception:
  state('SUPERVISOR_ERROR',traceback=traceback.format_exc());raise
