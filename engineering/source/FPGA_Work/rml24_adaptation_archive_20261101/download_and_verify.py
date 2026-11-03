from pathlib import Path,PurePosixPath
import http.client,json,time,hashlib,tarfile,os
p=Path(__file__).parent;token=json.loads((p/'LOCAL_CONFIG.json').read_text())['token']
def connect(route):
 c=http.client.HTTPConnection('192.168.126.49',8768,timeout=30,source_address=('192.168.126.10',0));c.request('GET','/'+token+'/'+route);r=c.getresponse();assert r.status==200,r.status;return c,r
for _ in range(90):
 try:c,r=connect('manifest');raw=r.read();c.close();meta=json.loads(raw);break
 except (OSError,http.client.HTTPException):time.sleep(5)
else:raise RuntimeError('archive readiness timeout')
(p/'MANIFEST.json').write_bytes(raw);c,r=connect('archive');target=p/'research_iq.tar.gz.part';h=hashlib.sha256()
with target.open('wb') as f:
 while True:
  b=r.read(1048576)
  if not b:break
  f.write(b);h.update(b)
 f.flush();os.fsync(f.fileno())
c.close();assert h.hexdigest()==meta['archive_sha256'] and target.stat().st_size==meta['archive_size'];expected=meta['files'];seen=set();total=0
with tarfile.open(target,'r:gz') as t:
 for m in t:
  rel=PurePosixPath(m.name);assert not rel.is_absolute() and '..' not in rel.parts and m.isfile() and m.name in expected and m.name not in seen;f=t.extractfile(m);hh=hashlib.sha256();size=0
  for b in iter(lambda:f.read(1048576),b''):hh.update(b);size+=len(b)
  assert hh.hexdigest()==expected[m.name]['sha256'] and size==expected[m.name]['size'];seen.add(m.name);total+=size
assert seen==set(expected);os.replace(target,p/'research_iq.tar.gz');proof=dict(passed=True,manifest_sha256=hashlib.sha256(raw).hexdigest(),archive_sha256=h.hexdigest(),verified_files=len(seen),verified_bytes=total,computer_archive=str(p/'research_iq.tar.gz'));(p/'VERIFIED.json').write_text(json.dumps(proof,indent=2));print('ARCHIVE_PC_FULLY_VERIFIED',len(seen),total,flush=True)
