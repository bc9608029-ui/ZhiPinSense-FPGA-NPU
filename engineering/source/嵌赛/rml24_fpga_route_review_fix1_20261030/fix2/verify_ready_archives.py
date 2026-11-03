"""Independent clean extraction and entry-point preflight; no devices."""
import hashlib,json,os,subprocess,tempfile,zipfile
from pathlib import Path
root=Path('F:/嵌赛')
receipt=json.loads((root/'rml24_test_readiness_20261030_RECEIPT.json').read_text(encoding='utf8'))
results=[]
for row in receipt['packages']:
 archive=Path(row['file'])
 assert hashlib.sha256(archive.read_bytes()).hexdigest()==row['sha256']
 with tempfile.TemporaryDirectory(prefix='ready_extract_',dir=root) as temp:
  target=Path(temp)
  with zipfile.ZipFile(archive) as z:
   for name in z.namelist():
    resolved=(target/name).resolve()
    assert resolved.is_relative_to(target.resolve())
   z.extractall(target)
  tree=target/'rml24_test_readiness_20261030'
  for line in (tree/'SHA256SUMS.txt').read_text(encoding='utf8').splitlines():
   h,name=line.split('  ',1)
   assert hashlib.sha256((tree/name).read_bytes()).hexdigest()==h
  r=subprocess.run(['D:/Anaconda/python.exe','-I',str(tree/'preflight.py')],capture_output=True,text=True,
                   env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
  assert r.returncode==0,r.stderr
  results.append(dict(file=archive.name,unpack_sha='PASS',clean_entry_preflight=json.loads(r.stdout)))
print(json.dumps(results,indent=2))
(root/'rml24_test_readiness_20261030_CLEAN_VERIFY.json').write_text(json.dumps(results,indent=2),encoding='utf8')
