from pathlib import Path
import json,hashlib,tarfile,re,http.server,socketserver,sys
root=Path('/root/rml24_gain_only_clipguard_rf_20261101').resolve();out=Path('/root/rml24_gain_headroom_archive_20261101');out.mkdir(exist_ok=True);archive=out/'raw_gain_pairs.tar.gz';manifest=out/'MANIFEST.json';token=sys.argv[1];assert re.fullmatch('[0-9a-f]{32}',token);assert json.loads((root/'CLASSIFICATION_RESULT.json').read_text())['guard_clean'];files=[f for f in sorted(root.glob('pair_*.npy')) if re.fullmatch(r'pair_[0-9]+_(initial|final)[.]npy',f.name)];assert files
entries={}
for f in files:
 assert f.resolve().parent==root and f.is_file() and not f.is_symlink();entries[f.name]=dict(size=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest())
v=dict(root=str(root),files=entries);manifest.write_text(json.dumps(v,indent=2))
with tarfile.open(str(archive),'w:gz',compresslevel=1) as t:
 t.add(str(manifest),arcname='MANIFEST.json',recursive=False)
 for f in files:t.add(str(f),arcname='raw/'+f.name,recursive=False)
sha=hashlib.sha256(archive.read_bytes()).hexdigest();ready=dict(archive_sha256=sha,size=archive.stat().st_size,files=len(files),path='/'+token+'/raw_gain_pairs.tar.gz',manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest());(out/'READY.json').write_text(json.dumps(ready))
class Handler(http.server.BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_GET(self):
  if self.client_address[0]!='192.168.126.10' or self.path!=ready['path']:self.send_error(404);return
  self.send_response(200);self.send_header('Content-Type','application/octet-stream');self.send_header('Content-Length',str(archive.stat().st_size));self.end_headers()
  with archive.open('rb') as f:
   while True:
    b=f.read(1024*256)
    if not b:break
    self.wfile.write(b)
  self.server.served=True
class Server(socketserver.TCPServer):allow_reuse_address=True
with Server(('192.168.126.49',8768),Handler) as server:
 server.timeout=120;server.served=False;print('ARCHIVE_READY '+json.dumps(ready),flush=True);server.handle_request();(out/'SERVER_CLOSED.json').write_text(json.dumps(dict(served=server.served)))
