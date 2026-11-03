from pathlib import Path
import tarfile,hashlib,zipfile,json
r=Path(r'E:\rml24_three_modes_execution_20261029');p=r/'candidate.zip';assert hashlib.sha256(p.read_bytes()).hexdigest()=='19724dc5c1360fb4add86825bfc016b362fcbd47bdc68eda3e051d33e97a8173'
with zipfile.ZipFile(p) as z:
 checks=[]
 for line in z.read('SHA256SUMS.txt').decode().splitlines():
  h,n=line.split(None,1);n=n.lstrip('* ');assert hashlib.sha256(z.read(n)).hexdigest()==h,n;checks.append(n)
 assert len(checks)==187
print('ARCHIVE_SHA_AND_187_FILES_PASS')
b=Path(r'E:\rml24_fpga_execution_20261027\baseline_backup\runtime_before.tar.gz')
with tarfile.open(str(b)) as t:
 for m in t.getmembers():
  if m.name.endswith('/build/npu_stream'):
   h=hashlib.sha256(t.extractfile(m).read()).hexdigest();assert h=='cc88cb0bf5cde766937d011978314b7dafd1122d0f18e1cbda731ec2f7a440d8';print('NPU_ARCHIVED_BASELINE_MATCH',m.name,h)
(r/'local_preflight.json').write_text(json.dumps(dict(package_sha_verified=True,content_files_verified=187,npu_expected_sha256='cc88cb0bf5cde766937d011978314b7dafd1122d0f18e1cbda731ec2f7a440d8',board_build_pending=True),indent=2))
