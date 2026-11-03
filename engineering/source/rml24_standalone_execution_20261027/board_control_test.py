import socket,json,time
from pathlib import Path
out=Path('/root/rml24_standalone_execution_20261027/control_test.json')
s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);s.settimeout(40)
s.connect('/run/rml24_standalone_control.sock');f=s.makefile('rwb',buffering=0)
rows=[]
def request(command,expect):
    f.write((command+'\n').encode());reply=[]
    while True:
        line=f.readline().decode().strip()
        if not line:raise RuntimeError('control EOF')
        reply.append(line)
        if not line.startswith('OK accepted '):break
    ok=expect in reply[-1]
    rows.append(dict(command=command,replies=reply,passed=ok))
    if not ok:raise RuntimeError(rows[-1])
try:
    request('GET_TUNING','tuning=1')
    request('SET_FIXED_HZ 2401000000','applied_fixed_hz=2401000000')
    request('GET_TUNING','actual_lo_hz=2401000000')
    request('SET_FIXED_HZ 2500000001','OUT_OF_RANGE')
    request('GET_TUNING','actual_lo_hz=2401000000')
    request('SET_SCAN_RANGE_HZ 2400000000 2395000000 1000000','START_GE_STOP')
    request('SET_SCAN_RANGE_HZ 2395000000 2405000000 3000000','STEP_INVALID')
    request('SET_MODE AUTO_LOCK','unsupported_mode')
    request('STOP','OK applied');request('STATUS','applied_running=0')
    request('SET_SCAN_RANGE_HZ 2397000000 2403000000 1000000','scan_points=7')
    request('SET_MODE BAND_SCAN','OK applied')
    request('START','OK applied');request('STATUS','applied_mode=BAND_SCAN')
    time.sleep(3)
    request('STOP','OK applied');request('SET_MODE FIXED','OK applied')
    request('SET_FIXED_HZ 2400000000','applied_fixed_hz=2400000000')
    request('START','OK applied');request('STATUS','applied_running=1')
finally:
    out.write_text(json.dumps(dict(rows=rows,passed=sum(r['passed'] for r in rows),total=len(rows)),indent=2))
    print(out.read_text(),flush=True);f.close();s.close()
