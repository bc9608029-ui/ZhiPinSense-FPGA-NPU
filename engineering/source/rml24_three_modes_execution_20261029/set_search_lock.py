import socket,json
from pathlib import Path
r=Path('/root/rml24_three_modes_execution_20261029');s=socket.socket(socket.AF_UNIX);s.settimeout(35);s.connect(str(r/'ui_progress03/control.sock'));f=s.makefile('rwb');f.write(b'SET_MODE BAND_SCAN\n');f.flush();a=f.readline().decode();b=f.readline().decode();assert 'OK accepted' in a and 'OK applied' in b,(a,b);f.write(b'GET_TUNING\n');f.flush();c=f.readline().decode();print(a,b,c);(r/'REACQUIRE_MODE_SETUP.json').write_text(json.dumps([a,b,c]));s.close()
