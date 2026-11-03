from pathlib import Path
import hashlib,tarfile,shutil
r=Path(r'E:\嵌赛\rml24_boot_persistence_20261027');c=r/'candidate';shutil.copyfile(r/'candidate_payload.tar.gz',r/'candidate_payload_attempt1_crlf.tar.gz')
for p in c.rglob('*'):
 if p.is_file() and p.suffix in ('.txt','.sh','.service'):p.write_bytes(p.read_bytes().replace(b'\r\n',b'\n'))
(c/'SHA256SUMS.txt').write_bytes(('\n'.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(c)).replace('\\','/') for p in sorted(c.rglob('*')) if p.is_file() and p.name!='SHA256SUMS.txt')+'\n').encode('ascii'))
with tarfile.open(r/'candidate_payload.tar.gz','w:gz') as t:
 for p in sorted(c.rglob('*')):
  if p.is_file():t.add(p,arcname=str(p.relative_to(c)).replace('\\','/'))
shutil.copyfile(r/'candidate_payload.tar.gz',r'E:\嵌赛\rml24_stage7_execution_20261027\transfer\boot_candidate_payload.tar.gz');print('PAYLOAD_SHA',hashlib.sha256((r/'candidate_payload.tar.gz').read_bytes()).hexdigest())