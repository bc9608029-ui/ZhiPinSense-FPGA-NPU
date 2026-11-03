from pathlib import Path
import json,subprocess,time,re,secrets,http.client,hashlib,tarfile
p=Path(__file__).parent;token=secrets.token_hex(16)
def ps(args):
 q=subprocess.run(['powershell','-NoProfile','-File']+args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);s=q.stdout.decode('utf8',errors='replace');assert q.returncode==0,s;return s
def board(cmd,seconds=3):return ps(['E:/FPGA_Work/rml24_lockpilot_formal_prep_20261101/serial_exclusive.ps1','-Command',cmd,'-Seconds',str(seconds)])
(p/'START.txt').write_text(board('nohup python3 /root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031/archive_gain_pairs.py '+token+' > /root/gain_pairs_archive_20261101.log 2>&1 < /dev/null &'))
for _ in range(30):
 text=board('tail -n 3 /root/gain_pairs_archive_20261101.log',2);m=re.search(r'(?:^|[\r\n])ARCHIVE_READY (\{[^\r\n]+\})',text)
 if m:break
 if 'Traceback' in text or 'Error' in text:raise RuntimeError(text)
 time.sleep(2)
else:raise RuntimeError('archive service not ready')
meta=json.loads(m[1]);(p/'BOARD_READY.json').write_text(json.dumps(meta,indent=2));archive=p/'raw_gain_pairs.tar.gz';assert not archive.exists();c=http.client.HTTPConnection('192.168.126.49',8768,timeout=60,source_address=('192.168.126.10',0));c.request('GET',meta['path']);response=c.getresponse();assert response.status==200
with archive.open('wb') as f:
 while True:
  block=response.read(1024*1024)
  if not block:break
  f.write(block)
c.close();assert archive.stat().st_size==meta['size'];digest=hashlib.sha256(archive.read_bytes()).hexdigest();assert digest==meta['archive_sha256']
with tarfile.open(str(archive),'r:gz') as t:
 members=t.getmembers();assert all(m.isfile() for m in members);names=[m.name for m in members];assert len(names)==len(set(names));manifest_bytes=t.extractfile('MANIFEST.json').read();manifest=json.loads(manifest_bytes);assert hashlib.sha256(manifest_bytes).hexdigest()==meta['manifest_sha256'];assert len(manifest['files'])==meta['files'];assert set(names)=={'MANIFEST.json'}|{'raw/'+n for n in manifest['files']}
 for name,entry in manifest['files'].items():
  assert re.fullmatch(r'pair_[0-9]+_(initial|final)[.]npy',name);b=t.extractfile('raw/'+name).read();assert len(b)==entry['size'] and hashlib.sha256(b).hexdigest()==entry['sha256']
proof=dict(all_members_verified=True,files=len(manifest['files']),archive_sha256=digest,manifest_sha256=meta['manifest_sha256'],pc_archive=str(archive));(p/'GAIN_ARCHIVE_VERIFIED.json').write_text(json.dumps(proof,indent=2));ps(['E:/rml24_three_modes_execution_20261029/upload.ps1','-Local',str(p/'GAIN_ARCHIVE_VERIFIED.json'),'-Remote','/root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031/GAIN_ARCHIVE_VERIFIED.json']);text=board('python3 /root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031/cleanup_verified_gain_pairs.py',20);(p/'CLEANUP.txt').write_text(text);assert re.search(r'(?:^|[\r\n])VERIFIED_GAIN_RAW_ARCHIVED ',text),text;print('GAIN_RAW_PC_ARCHIVE_VERIFIED_AND_BOARD_SPACE_RELEASED',proof['files'],digest,flush=True)
