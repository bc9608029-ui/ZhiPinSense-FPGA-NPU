from http.server import HTTPServer,BaseHTTPRequestHandler
from pathlib import Path
import time,shutil
root=Path('/root/rml24_fpga_execution_20261027/baseline')
allowed={'runtime_before.tar.gz','sd_boot_before.tar.gz','archive_sha256.txt','sd_boot_identity.txt','context.txt'}
class H(BaseHTTPRequestHandler):
 def do_GET(self):
  name=self.path[len('/rml24-b43d91-backup/'):]
  if self.client_address[0]!='192.168.126.50' or not self.path.startswith('/rml24-b43d91-backup/') or name not in allowed:
   self.send_error(403);return
  p=root/name;self.send_response(200);self.send_header('Content-Length',str(p.stat().st_size));self.end_headers()
  with p.open('rb') as f:shutil.copyfileobj(f,self.wfile)
  self.server.completed+=1
server=HTTPServer(('192.168.126.49',39131),H);server.timeout=2;server.completed=0;end=time.monotonic()+120
while time.monotonic()<end and server.completed<5:server.handle_request()
server.server_close();print('BOUNDED_BACKUP_SERVER_CLOSED',flush=True)