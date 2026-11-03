import hashlib,json,re,subprocess,tarfile,urllib.request
from pathlib import Path
r=Path(__file__).parent
command='cat /root/rml24_mainchain_diagnostic_20261028/archive_info.log; cat /root/rml24_mainchain_diagnostic_20261028/export_server.log'
v=subprocess.run(['powershell','-NoProfile','-File',str(r.parent/'scan_exec_20261027/serial.ps1'),
                  '-Command',command,'-Seconds','3'],capture_output=True)
text=v.stdout.decode(errors='replace')
infos=re.findall(r'\{"archive":[^\r\n]+\}',text)
if not infos or 'ONE_FILE_SERVER_READY' not in text:raise RuntimeError('Archive/server not ready: '+text[-1600:])
info=json.loads(infos[-1]);(r/'archive_info.json').write_text(json.dumps(info,indent=2))
if not 0<info['bytes']<1073741824:raise RuntimeError('Unexpected archive size')
out=r/'diag_fixed01_evidence.tar.gz'
if out.exists():raise RuntimeError('Refusing to replace collected archive')
digest=hashlib.sha256();size=0
with urllib.request.urlopen('http://192.168.126.49:39132/diag_fixed01_evidence.tar.gz',timeout=60) as response:
    if int(response.headers['Content-Length'])!=info['bytes']:raise RuntimeError('Length mismatch')
    with out.with_suffix('.part').open('wb') as f:
        while True:
            chunk=response.read(1048576)
            if not chunk:break
            f.write(chunk);digest.update(chunk);size+=len(chunk)
if size!=info['bytes'] or digest.hexdigest()!=info['sha256']:raise RuntimeError('Archive SHA mismatch')
out.with_suffix('.part').replace(out)
dest=r/'board';dest.mkdir(exist_ok=False)
with tarfile.open(out) as t:
    for m in t.getmembers():
        if not (m.isfile() or m.isdir()):
            raise RuntimeError('Unsafe archive member '+m.name)
        try:(dest/m.name).resolve().relative_to(dest.resolve())
        except ValueError:raise RuntimeError('Archive traversal '+m.name)
    t.extractall(dest)
base=dest/'diag_fixed01'
hashes=json.loads((base/'evidence_SHA256.json').read_text())
for name,expected in hashes.items():
    if hashlib.sha256((base/name).read_bytes()).hexdigest()!=expected:raise RuntimeError('File SHA mismatch '+name)
print('EVIDENCE_DOWNLOAD_PASS bytes=%d files=%d sha256=%s'%(size,len(hashes),digest.hexdigest()),flush=True)
