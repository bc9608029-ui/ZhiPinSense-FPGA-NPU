from pathlib import Path
import tarfile,hashlib,json,time,os
from http.server import HTTPServer,BaseHTTPRequestHandler
roots=[Path('/root')/n for n in ('rml24_weak_bandwidth_rf_20261101','rml24_gainfreeze_range_paired_20261101','rml24_weak_adaptive_rf_20261101')];out=Path('/root/rml24_adaptation_archive_20261101');out.mkdir(exist_ok=True);token='REDACTED_LOCAL_ACCESS_TOKEN_SET_AT_RUNTIME'
assert all((r/'CLASSIFICATION_RESULT.json').is_file() for r in roots)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
files={}
for root in roots:
 for f in sorted(root.rglob('*')):
  assert not f.is_symlink(),str(f)
  if f.is_file():files[str(f.relative_to('/root'))]=dict(sha256=sha(f),size=f.stat().st_size)
archive=out/'research_iq.tar.gz';assert not archive.exists()
with tarfile.open(archive,'w:gz',compresslevel=1) as t:
 for rel in files:t.add('/root/'+rel,arcname=rel,recursive=False)
meta=dict(files=files,archive_sha256=sha(archive),archive_size=archive.stat().st_size,models_included=False,scope=[str(r) for r in roots]);manifest=out/'MANIFEST.json';manifest.write_text(json.dumps(meta,indent=2));done=[False]
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  if self.client_address[0]!='192.168.126.10' or not self.path.startswith('/'+token+'/'):self.send_error(403);return
  route=self.path.split('/')[-1];path=manifest if route=='manifest' else archive if route=='archive' else None
  if path is None:self.send_error(404);return
  self.send_response(200);self.send_header('Content-Length',str(path.stat().st_size));self.end_headers()
  with path.open('rb') as f:
   for b in iter(lambda:f.read(1048576),b''):self.wfile.write(b)
  if route=='archive':done[0]=True
 def log_message(self,*args):pass
server=HTTPServer(('192.168.126.49',8768),Handler);server.timeout=1;end=time.monotonic()+900;print('ARCHIVE_READY',archive.stat().st_size,len(files),flush=True)
try:
 while not done[0] and time.monotonic()<end:server.handle_request()
finally:server.server_close()
print('ARCHIVE_TRANSFER_SERVER_CLOSED',flush=True)
