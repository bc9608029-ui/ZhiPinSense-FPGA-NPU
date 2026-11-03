"""Temporary system-awake request while this exact native test process lives."""
import ctypes,json,sys,time
from pathlib import Path
pid=int(sys.argv[1]);root=Path(__file__).resolve().parent
k=ctypes.WinDLL('kernel32',use_last_error=True)
k.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong];k.OpenProcess.restype=ctypes.c_void_p
k.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong];k.WaitForSingleObject.restype=ctypes.c_ulong
k.CloseHandle.argtypes=[ctypes.c_void_p]
k.SetThreadExecutionState.argtypes=[ctypes.c_ulong];k.SetThreadExecutionState.restype=ctypes.c_ulong
handle=k.OpenProcess(0x100000,False,pid)
if not handle:raise OSError(ctypes.get_last_error(),'cannot observe test process')
try:
 if not k.SetThreadExecutionState(0x80000001):raise OSError(ctypes.get_last_error(),'awake request rejected')
 (root/'AWAKE_REQUEST.json').write_text(json.dumps(dict(test_pid=pid,system_required=True,display_required=False,power_plan_changed=False)))
 while k.WaitForSingleObject(handle,30000)==258:pass
finally:
 k.SetThreadExecutionState(0x80000000);k.CloseHandle(handle)
 (root/'AWAKE_REQUEST.json').write_text(json.dumps(dict(test_pid=pid,system_required=False,power_plan_changed=False)))
