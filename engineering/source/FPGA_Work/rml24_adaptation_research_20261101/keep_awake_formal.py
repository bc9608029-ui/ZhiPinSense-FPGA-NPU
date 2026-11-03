from pathlib import Path
import ctypes,time,json
p=Path('E:/FPGA_Work/rml24_adaptation_research_20261101');pid=int((p/'FORMAL_CONTROLLER_PID.txt').read_text(encoding='utf-8-sig'));k=ctypes.windll.kernel32;k.OpenProcess.restype=ctypes.c_void_p;k.OpenProcess.argtypes=[ctypes.c_uint,ctypes.c_int,ctypes.c_uint];k.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_uint];k.CloseHandle.argtypes=[ctypes.c_void_p];handle=k.OpenProcess(0x100000,0,pid);assert handle;assert k.SetThreadExecutionState(0x80000001)!=0;end=time.monotonic()+3*3600;(p/'SLEEP_GUARD.json').write_text(json.dumps(dict(active=True,parent_pid=pid,display_required=False,max_hours=3)))
try:
 while time.monotonic()<end and k.WaitForSingleObject(handle,0)==258:time.sleep(10)
finally:
 k.SetThreadExecutionState(0x80000000);k.CloseHandle(handle);(p/'SLEEP_GUARD.json').write_text(json.dumps(dict(active=False,parent_pid=pid,display_required=False)))
