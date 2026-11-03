"""Deterministic PC and board packages with independent per-member verification."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import hashlib,json,zipfile
from common import ROOT,sha,write

def files(board):
 out={}
 for p in sorted(ROOT.rglob('*')):
  if not p.is_file():continue
  rel=p.relative_to(ROOT).as_posix()
  if '__pycache__' in p.parts or p.suffix in ('.pyc','.zip') or rel=='SHA256SUMS.txt':continue
  if rel=='evidence/test_protocol':continue
  if board and rel.startswith('tx/assets/'):continue
  if any(x.startswith(('offline_','tmp')) for x in p.relative_to(ROOT).parts):continue
  out[rel]=p.read_bytes()
 return out
def build(board):
 members=files(board)
 members['SHA256SUMS.txt']=''.join(hashlib.sha256(data).hexdigest()+'  '+name+'\n' for name,data in members.items()).encode()
 archive=ROOT.parent/(ROOT.name+('_board' if board else '_pc')+'.zip')
 with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for name,data in members.items():
   info=zipfile.ZipInfo(ROOT.name+'/'+name,date_time=(2026,10,30,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
   info.external_attr=0o100644<<16;z.writestr(info,data)
 with zipfile.ZipFile(archive) as z:
  if z.testzip():raise RuntimeError('CRC error')
  manifest=z.read(ROOT.name+'/SHA256SUMS.txt').decode()
  expected=set()
  for line in manifest.splitlines():
   h,name=line.split('  ',1);expected.add(ROOT.name+'/'+name)
   if hashlib.sha256(z.read(ROOT.name+'/'+name)).hexdigest()!=h:raise RuntimeError('member SHA mismatch')
  if set(z.namelist())!=expected|{ROOT.name+'/SHA256SUMS.txt'}:raise RuntimeError('member set mismatch')
  if board and any('/tx/assets/' in name for name in z.namelist()):raise RuntimeError('private TX IQ leaked into board package')
 (archive.with_suffix('.zip.sha256')).write_text(sha(archive)+'  '+archive.name+'\n',encoding='ascii')
 return dict(file=str(archive),sha256=sha(archive),bytes=archive.stat().st_size,
             content_files=len(members)-1,independent_zip_crc_and_sha='PASS',tx_payload_included=not board)
def main():
 receipt=dict(state='OFFLINE_TEST_PREP_COMPLETE_TARGET_PREFLIGHT_REQUIRED',
              packages=[build(False),build(True)],board_tested=False,rf_tested=False,
              production_receiver_integrated=False)
 write(ROOT.parent/(ROOT.name+'_RECEIPT.json'),receipt)
 print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
