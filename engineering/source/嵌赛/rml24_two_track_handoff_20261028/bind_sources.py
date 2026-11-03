#!/usr/bin/env python3
from pathlib import Path
import hashlib,json
items=[
 Path(r'F:\rml24_standalone_execution_20261027\NEXT_AGENT_HANDOFF.md'),
 Path(r'F:\rml24_standalone_execution_20261027\FINAL_TEST_SUMMARY.json'),
 Path(r'F:\rml24_standalone_execution_20261027\formal_fixed01_score.json'),
 Path(r'F:\rml24_standalone_execution_20261027\formal_scan01_score.json'),
 Path(r'F:\scan_exec_20261027\FINAL_SCAN_AUTOTEST_SUMMARY.json')]
out=[]
for p in items:
    if not p.is_file(): raise SystemExit(f'MISSING {p}')
    out.append({'path':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
Path(__file__).with_name('SOURCE_BINDING.json').write_text(json.dumps({'sources':out},indent=2)+'\n',encoding='utf-8')
print('SOURCE_BINDING result=PASS files=5')
