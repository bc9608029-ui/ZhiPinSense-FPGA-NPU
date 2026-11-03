from pathlib import Path
import hashlib,difflib
r=Path(r'E:\rml24_ac_execution_20261029');p=r/'board_base_ui_event.py';b=p.read_bytes();print('ACTUAL',hashlib.sha256(b).hexdigest(),'CRLF',hashlib.sha256(b.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')).hexdigest())
q=Path(r'E:\嵌赛\rml24_ac_integration_20261029\overlay\rml24_final\runtime\ui_event.py');d=''.join(difflib.unified_diff(b.decode().splitlines(True),q.read_text(encoding='utf-8').splitlines(True),fromfile='board_base',tofile='ac_overlay'))
(r/'ui_event_diff.txt').write_text(d,encoding='utf-8');print(d[:14000])
