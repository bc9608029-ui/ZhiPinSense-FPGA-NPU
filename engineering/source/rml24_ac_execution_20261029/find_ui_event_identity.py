from pathlib import Path
import hashlib
for p in Path(r'E:\??').rglob('ui_event.py'):
 b=p.read_bytes();h=hashlib.sha256(b).hexdigest()
 if h.startswith(('41c475','be1f0a')) or hashlib.sha256(b.replace(b'\r\n',b'\n')).hexdigest().startswith(('41c475','be1f0a')): print(str(p),h,'LF',hashlib.sha256(b.replace(b'\r\n',b'\n')).hexdigest())
