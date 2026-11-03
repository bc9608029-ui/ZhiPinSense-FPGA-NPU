from pathlib import Path
import socket,sys,json,subprocess
pid=int(subprocess.check_output(['systemctl','show','rml24-range-test','-p','MainPID','--value']).strip());args=Path('/proc/%d/cmdline'%pid).read_bytes().decode().strip('\0').split('\0');r=Path(args[args.index('--run')+1]);s=socket.socket(socket.AF_UNIX);s.settimeout(45);s.connect(str(r/'control.sock'));f=s.makefile('rwb');c=' '.join(sys.argv[1:]);f.write((c+'\n').encode());f.flush()
while True:
 t=f.readline().decode().strip();print(t,flush=True)
 if 'accepted' not in t:break
assert t.startswith('OK'),t
if c.startswith('SET_FIXED_HZ'):
 rows=(r/'capture/records.jsonl').read_text().splitlines();Path('/root/rml24_range_expansion_20261101/mark.json').write_text(json.dumps(dict(run=str(r),first=len(rows),hz=int(sys.argv[2]))))
