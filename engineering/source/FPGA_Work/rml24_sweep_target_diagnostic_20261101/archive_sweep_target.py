from pathlib import Path
import json,hashlib,tarfile,re,http.server,socketserver,sys
root=Path('/root/rml24_sweep_target_diagnostic_20261101/runs/sweep6/capture').resolve();out=root.parent/'export';out.mkdir(exist_ok=True);archive=out/'sweep_raw_evidence.tar.gz';manifest=out/'MANIFEST.json';token=sys.argv[1];assert re.fullmatch('[0-9a-f]{32}',token);assert json.loads((root.parent/'FORMAL_RESTORE.json').read_text())['health']['ready'];assert json.loads((root.parent/'supervisor.json').read_text())['clean_stop'];files=[f for f in sorted(root.iterdir()) if re.fullmatch(r'[0-9]{6}[.](raw[.]npy|inputs[.]bin)',f.name) or f.name in ('records.jsonl','final.json','restore.json','spectrum_backend.jsonl','status.json')];assert any(f.name.endswith('.raw.npy') for f in files)

entries={}
for f in files:
 assert f.resolve().parent==root and f.is_file() and not f.is_symlink();entries[f.name]=dict(size=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest())
v=dict(root=str(root),files=entries);manifest.write_text(json.dumps(v,indent=2))
with tarfile.open(str(archive),'w:gz',compresslevel=1) as t:
 t.add(str(manifest),arcname='MANIFEST.json',recursive=False)
 for f in files:t.add(str(f),arcname='raw/'+f.name,recursive=False)
sha=hashlib.sha256(archive.read_bytes()).hexdigest();ready=dict(archive_sha256=sha,size=archive.stat().st_size,files=len(files),path='/'+token+'/sweep_raw_evidence.tar.gz',manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest());(out/'READY.json').write_text(json.dumps(ready))
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
