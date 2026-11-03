from pathlib import Path
import hashlib,zipfile
ROOT=Path(__file__).resolve().parent
def files():
 return sorted(p for p in ROOT.rglob('*') if p.is_file()
   and not any(k in p.parts for k in ['__pycache__','_tmp','runs','.pytest_cache'])
   and p.name not in ['SHA256SUMS.txt','preview.png'])
selected=files()
manifest=''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(ROOT).as_posix()+'\n' for p in selected)
(ROOT/'SHA256SUMS.txt').write_text(manifest,encoding='utf8')
out=ROOT.parent/'rml24_tx_console_20261029.zip'
with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for p in sorted(selected+[ROOT/'SHA256SUMS.txt']):
  info=zipfile.ZipInfo(ROOT.name+'/'+p.relative_to(ROOT).as_posix(),(1980,1,1,0,0,0))
  info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
  z.writestr(info,p.read_bytes())
with zipfile.ZipFile(out) as z:
 assert z.testzip() is None
 for line in manifest.splitlines():
  digest,name=line.split('  ',1)
  assert hashlib.sha256(z.read(ROOT.name+'/'+name)).hexdigest()==digest,name
digest=hashlib.sha256(out.read_bytes()).hexdigest()
out.with_suffix('.zip.sha256').write_text(digest+'  '+out.name+'\n',encoding='ascii')
print('TX_CONSOLE_PACKAGE PASS files='+str(len(selected))+' sha256='+digest)
