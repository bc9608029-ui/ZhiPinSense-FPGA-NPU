"""Serve one generated evidence archive to the user's wired PC, then close."""
import hashlib,http.server,json,time
from pathlib import Path
root=Path('/root/rml24_mainchain_diagnostic_20261028')
path=root/'diag_fixed01_evidence.tar.gz'
done=False
class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global done
        if self.client_address[0]!='192.168.126.50' or self.path!='/diag_fixed01_evidence.tar.gz':
            self.send_error(403);return
        self.send_response(200);self.send_header('Content-Length',str(path.stat().st_size));self.end_headers()
        try:
            with path.open('rb') as f:
                for chunk in iter(lambda:f.read(1048576),b''):self.wfile.write(chunk)
            self.wfile.flush();done=True
        except (BrokenPipeError,ConnectionResetError):pass
server=http.server.HTTPServer(('192.168.126.49',39132),Handler);server.timeout=5
print('ONE_FILE_SERVER_READY port=39132 allowed_pc=192.168.126.50',flush=True)
deadline=time.monotonic()+180
try:
    while not done and time.monotonic()<deadline:server.handle_request()
finally:server.server_close()
print('ONE_FILE_SERVER_CLOSED sent=%d'%done,flush=True)
