#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,subprocess,sys,zipfile
HERE=Path(__file__).resolve().parent; BASE=HERE.parent
for script in [BASE/'rml24_mainchain_freeze_prep_20261028/tests/selftest.py',BASE/'rml24_fpga_smart_scan_prep_20261028/scripts/selftest.py']:
    p=subprocess.run([sys.executable,str(script)]); assert p.returncode==0
manifest=json.loads((HERE/'ARTIFACTS.json').read_text())
for a in manifest['artifacts']:
    p=BASE/a['file']; assert hashlib.sha256(p.read_bytes()).hexdigest()==a['sha256']
    with zipfile.ZipFile(p) as z: assert z.testzip() is None
print('TWO_TRACK_VERIFY result=PASS artifacts=2')
