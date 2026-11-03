from pathlib import Path
import socket,sys,json,subprocess
pid=int(subprocess.check_output(['systemctl','show','rml24-integrated','-p','MainPID','--value']).strip());args=Path('/proc/%d/cmdline'%pid).read_bytes().decode().strip('\0').split('\0');r=Path(args[args.index('--run')+1]);s=socket.socket(socket.AF_UNIX);s.settimeout(45);s.connect(str(r/'control.sock'));f=s.makefile('rwb');c=' '.join(sys.argv[1:]);f.write((c+'\n').encode());f.flush()
while True:
 t=f.readline().decode().strip();print(t,flush=True)
 if 'accepted' not in t:break
assert t.startswith('OK'),t
