from pathlib import Path
import argparse,json,time,sys,hashlib
from http.server import HTTPServer,BaseHTTPRequestHandler
sys.path.insert(0,'E:/FPGA_Work/rml24_timing_fix_20261031');from timing_contract import pc_monotonic_ns
p=argparse.ArgumentParser();p.add_argument('--token',required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--port',type=int,default=8765);a=p.parse_args();a.out.mkdir(exist_ok=True);bit=Path('E:/FPGA_Work/smartscan_prefetch_fix3_20261031/outputs/smartscan_fix3_candidate/smartscan_fix3_vendor_auto_disable_icap.bit');assert hashlib.sha256(bit.read_bytes()).hexdigest()=='f42dd12f03bf81c65978b7034b45808efd5035f6a358cc54710f2404530a057c'
class Handler(BaseHTTPRequestHandler):
 def allowed(self):return self.client_address[0]=='192.168.126.49' and self.path.startswith('/'+a.token+'/')
 def do_GET(self):
  if not self.allowed():self.send_error(403);return
  route=self.path.split('/')[-1]
  if route=='clock':body=json.dumps(dict(clock_id='windows-qpc',pc_qpc_ns=pc_monotonic_ns())).encode()
  elif route=='candidate.bit':body=bit.read_bytes()
  else:self.send_error(404);return
  self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
 def do_POST(self):
  if not self.allowed() or not self.path.endswith('/receipt'):self.send_error(403);return
  size=int(self.headers.get('Content-Length','0'))
  if size<=0 or size>65536:self.send_error(413);return
  value=json.loads(self.rfile.read(size));name='receipt_'+str(time.time_ns())+'.json';(a.out/name).write_text(json.dumps(value,indent=2),encoding='utf-8');(a.out/'LATEST_RECEIPT.json').write_text(json.dumps(value,indent=2),encoding='utf-8');self.send_response(200);self.end_headers();self.wfile.write(b'OK')
 def log_message(self,format,*args):print(format%args,flush=True)
server=HTTPServer(('192.168.126.10',a.port),Handler);server.timeout=1;deadline=time.monotonic()+1800;print('LIMITED_ARTIFACT_AND_BOOT_RECEIPT_SERVER_READY',flush=True)
while time.monotonic()<deadline and not (a.out/'STOP_SERVER.request').exists():server.handle_request()
server.server_close()
