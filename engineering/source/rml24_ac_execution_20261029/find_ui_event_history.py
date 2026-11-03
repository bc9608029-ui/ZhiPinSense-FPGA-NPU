from pathlib import Path
import hashlib
roots=[Path(r'E:\rml24_standalone_execution_20261027'),Path(r'E:\rml24_fpga_execution_20261027'),Path(r'E:\??\rml24_ac_integration_20261029')]
for root in roots:
 for p in root.rglob('ui_event.py'):
  b=p.read_bytes();print(str(p),len(b),hashlib.sha256(b).hexdigest())
