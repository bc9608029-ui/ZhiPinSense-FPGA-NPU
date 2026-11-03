import socket,json,time
from pathlib import Path
r=Path('/root/rml24_three_modes_execution_20261029');rows=[]
for i in range(3):
 s=socket.socket(socket.AF_UNIX);s.settimeout(5);s.connect(str(r/'ui_accept02/control.sock'));s.sendall(b'GET_TUNING\n');reply=s.recv(8192).decode();s.close();rows.append(reply);print(reply,flush=True);time.sleep(2)
(r/'PROGRESS_READBACK.json').write_text(json.dumps(rows,indent=2))
