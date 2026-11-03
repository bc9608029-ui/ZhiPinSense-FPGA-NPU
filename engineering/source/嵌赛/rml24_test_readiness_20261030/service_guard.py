"""Board-only exact service stop/restore; never disable/enable or broad-kill."""
import argparse,json,re,subprocess,sys
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--services',nargs='+',required=True)
 p.add_argument('--log',type=Path,required=True);p.add_argument('command',nargs=argparse.REMAINDER);a=p.parse_args()
 command=a.command[1:] if a.command[:1]==['--'] else a.command
 if not command or a.log.exists():raise ValueError('command and fresh log required')
 for name in a.services:
  if not re.fullmatch(r'[a-zA-Z0-9_.@-]+\.service',name):raise ValueError('exact .service names only')
 rows=[];stopped=[];rc=1;restore_errors=[]
 try:
  for name in a.services:
   s=subprocess.check_output(['systemctl','show',name,'--property=LoadState,ActiveState','--no-pager'],text=True)
   if 'LoadState=loaded' not in s:raise RuntimeError('unknown service '+name)
   active='ActiveState=active' in s;rows.append(dict(service=name,was_active=active))
   if active:
    stopped.append(name);subprocess.run(['systemctl','stop',name],check=True)
  rc=subprocess.run(command,check=False).returncode
 finally:
  for name in reversed(stopped):
   try:subprocess.run(['systemctl','start',name],check=True)
   except Exception as e:restore_errors.append(str(e))
  a.log.write_text(json.dumps(dict(services=rows,command=command,rc=rc,restore_errors=restore_errors),indent=2))
 return 1 if restore_errors else rc
if __name__=='__main__':sys.exit(main())
