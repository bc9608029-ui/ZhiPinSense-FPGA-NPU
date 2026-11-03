from pathlib import Path
from http.server import HTTPServer,BaseHTTPRequestHandler
import argparse,json,hashlib,os,sys,time,subprocess
ROOT=Path('/root/rml24_final_install_20261031')
p=argparse.ArgumentParser();p.add_argument('--staging',action='store_true');p.add_argument('--seconds',type=int,default=600);a=p.parse_args();config=json.loads((ROOT/'ACCEPTANCE_CONFIG.json').read_text());token=config['token'];release=Path(json.loads((ROOT/'STAGED.json').read_text())['release']);sys.path.insert(0,str(release));from collect_status import collect_status
stop=[False]
class Handler(BaseHTTPRequestHandler):
 def permitted(self):return self.client_address[0]=='192.168.126.10' and self.path.startswith('/'+token+'/')
 def do_GET(self):
  if not self.permitted():self.send_error(403);return
  route=self.path.split('/')[-1]
  if route=='clock':value=dict(clock_id='board-monotonic-v1',board_mono_ns=time.monotonic_ns(),board_boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
  elif route=='health':value=collect_status(release)
  elif route=='evidence':
   value=collect_status(release);value['rows']=[]
   if 'run' in value:
    p=Path(value['run'])/'capture/records.jsonl'
    if p.exists():
     for line in p.read_text().splitlines()[-100:]:
      try:
       row=json.loads(line);value['rows'].append(dict(frame_id=row['frame_id'],capture_monotonic_ns=row['capture_monotonic_ns'],clock_id=row['clock_id'],boot_id=row['boot_id'],scan_steps=row['scan_steps'],pred=row['candidate']['pred'],finite=row['candidate']['finite']))
      except (ValueError,KeyError):pass
  else:self.send_error(404);return
  body=json.dumps(value).encode();self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
 def do_POST(self):
  if not self.permitted():self.send_error(403);return
  route=self.path.split('/')[-1]
  if route=='done':stop[0]=True;self.send_response(200);self.end_headers();return
  if route!='candidate.bit' or not a.staging:self.send_error(404);return
  size=int(self.headers.get('Content-Length','0'))
  if not 1000000<size<9000000:self.send_error(413);return
  data=self.rfile.read(size);expected=json.loads((release/'PROMOTED_RELEASE.json').read_text())['boot']['candidate_bit_sha256']
  if len(data)!=size or hashlib.sha256(data).hexdigest()!=expected:self.send_error(400);return
  temp=ROOT/'new.bit.upload'
  with temp.open('wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
  os.replace(str(temp),str(ROOT/'new.bit'));self.send_response(200);self.end_headers();self.wfile.write(b'BIT_SHA_VERIFIED')
 def log_message(self,format,*args):print(format%args,flush=True)
server=HTTPServer(('192.168.126.49',8766),Handler);server.timeout=1;deadline=time.monotonic()+a.seconds;print('RESTRICTED_BOARD_ACCEPTANCE_SERVER_READY',flush=True)
rollback_needed=False;started=time.monotonic();last_check=0.0;last_ready=started
try:
 while time.monotonic()<deadline and not stop[0]:
  server.handle_request()
  if not a.staging and time.monotonic()-last_check>=10:
   last_check=time.monotonic()
   try:health=collect_status(release)
   except Exception as exc:health=dict(ready=False,error=str(exc))
   (ROOT/'BOOT_ACCEPTANCE_LATEST.json').write_text(json.dumps(health,indent=2))
   if health.get('ready'):last_ready=time.monotonic()
   elif config.get('rollback_on_health_failure') and time.monotonic()-last_ready>180:
    (ROOT/'BOOT_HEALTH_FAILED.json').write_text(json.dumps(health,indent=2));rollback_needed=True;break
finally:
 server.server_close()
 if not a.staging:subprocess.run(['systemctl','disable','rml24-boot-acceptance'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)

if rollback_needed:
 subprocess.run([sys.executable,str(ROOT/'rollback_release.py'),'restore-and-reboot'],check=True)
