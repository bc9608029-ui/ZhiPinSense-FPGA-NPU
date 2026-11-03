from pathlib import Path
import hashlib,json
r=Path('/root/rml24_ac_execution_20261029');d=r/'delivery/scripts';o=r/'launch_scripts';o.mkdir(exist_ok=False);report=[]
for p in d.iterdir():
 if p.suffix not in ['.py','.sh'] or '_compat_' in p.name or '_lf' in p.name:continue
 b=p.read_bytes();data=b.replace(b'\r\n',b'\n') if p.suffix=='.sh' else b
 q=o/p.name;q.write_bytes(data);q.chmod(0o755)
 report.append(dict(file=p.name,before=hashlib.sha256(b).hexdigest(),after=hashlib.sha256(data).hexdigest(),change='CRLF_TO_LF_ONLY' if b!=data else 'UNCHANGED'))
(r/'LAUNCH_SCRIPT_LINE_ENDINGS.json').write_text(json.dumps(report,indent=2));print('LAUNCH_COPIES_READY')
