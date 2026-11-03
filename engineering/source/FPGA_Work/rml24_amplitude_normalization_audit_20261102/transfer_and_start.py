from pathlib import Path
import threading,http.server,socketserver,subprocess,secrets,hashlib,json
p=Path(__file__).parent;token=secrets.token_hex(16);a=p/'blind_inputs.tar.gz';sha=hashlib.sha256(a.read_bytes()).hexdigest()
class H(http.server.BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_GET(self):
  if self.client_address[0]!='192.168.126.49' or self.path!='/'+token+'/blind_inputs.tar.gz':self.send_error(404);return
  self.send_response(200);self.send_header('Content-Length',str(a.stat().st_size));self.end_headers();self.wfile.write(a.read_bytes())
class S(socketserver.TCPServer):allow_reuse_address=True
server=S(('192.168.126.10',8770),H);server.timeout=180;thread=threading.Thread(target=server.handle_request);thread.start()
code="import urllib.request,pathlib,hashlib,tarfile,re,io; b=urllib.request.urlopen('http://192.168.126.10:8770/"+token+"/blind_inputs.tar.gz',timeout=60).read(); assert hashlib.sha256(b).hexdigest()=='"+sha+"'; p=pathlib.Path('/root/rml24_amplitude_normalization_audit_20261102/inputs'); p.mkdir(parents=True,exist_ok=False); t=tarfile.open(fileobj=io.BytesIO(b),mode='r:gz'); m=t.getmembers(); assert len(m)==240 and all(x.isfile() and re.fullmatch('[0-9]{3}[.]bin',x.name) and x.size==8192 for x in m); [(p/x.name).write_bytes(t.extractfile(x).read()) for x in m]; print('BLIND_INPUTS_SHA_VERIFIED')"
try:
 cmd='python3 -c '+"'"+code.replace("'", "'\\''")+"'"
 # shell quote using Python POSIX utility, not PowerShell interpolation
 import shlex;cmd='python3 -c '+shlex.quote(code)
 r=subprocess.run(['powershell','-NoProfile','-File','E:/FPGA_Work/rml24_lockpilot_formal_prep_20261101/serial_exclusive.ps1','-Command',cmd,'-Seconds','8'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT);(p/'TRANSFER_SERIAL.txt').write_bytes(r.stdout);assert r.returncode==0 and b'BLIND_INPUTS_SHA_VERIFIED\r\n' in r.stdout,r.stdout[-1500:]
finally:
 thread.join(timeout=185);server.server_close()
r=subprocess.run(['powershell','-NoProfile','-File','E:/rml24_three_modes_execution_20261029/upload.ps1','-Local',str(p/'replay_blind_normalization.py'),'-Remote','/root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031/replay_blind_normalization.py'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT);(p/'UPLOAD.txt').write_bytes(r.stdout);assert r.returncode==0
cmd='nohup /root/miniconda3/envs/torch_v2.0.1_aarch64/bin/python3 /root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031/replay_blind_normalization.py > /root/rml24_amplitude_normalization_audit_20261102/normalization.log 2>&1 < /dev/null &'
r=subprocess.run(['powershell','-NoProfile','-File','E:/FPGA_Work/rml24_lockpilot_formal_prep_20261101/serial_exclusive.ps1','-Command',cmd,'-Seconds','3'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT);(p/'START.txt').write_bytes(r.stdout);assert r.returncode==0
(p/'STATUS.json').write_text(json.dumps(dict(stage='BLIND_NPU_REPLAY_STARTED',no_rf=True,not_deployed=True)));print('BLIND_NORMALIZATION_REPLAY_STARTED',flush=True)
