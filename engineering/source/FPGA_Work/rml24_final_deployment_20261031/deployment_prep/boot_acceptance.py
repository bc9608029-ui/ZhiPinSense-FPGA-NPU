"""One-boot acceptance reporter. Never configures RF or opens an XRT Device."""
from pathlib import Path
import json,time,sys,urllib.request,subprocess
ROOT=Path('/root/rml24_final_install_20261031')
def main():
 config=json.loads((ROOT/'ACCEPTANCE_CONFIG.json').read_text());release=Path(json.loads((ROOT/'STAGED.json').read_text())['release']);sys.path.insert(0,str(release));from collect_status import collect_status
 base=config['base_url'];boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip();last=None
 for iteration in range(18):
  status=collect_status(release);samples=[]
  for _ in range(5):
   try:
    before=time.monotonic_ns()
    with urllib.request.urlopen(base+'/clock',timeout=2) as response:clock=json.load(response)
    after=time.monotonic_ns();assert clock['clock_id']=='windows-qpc';samples.append(dict(offset_ns=clock['pc_qpc_ns']-(before+after)//2,uncertainty_ns=(after-before)//2))
   except Exception:pass
  if samples:
   sample=min(samples,key=lambda x:x['uncertainty_ns']);status['calibration']=dict(sample,clock_id='windows-qpc-board-monotonic-v1',board_boot_id=boot)
  run=Path(status['run']) if 'run' in status else None
  if run and (run/'capture/records.jsonl').exists():
   lines=(run/'capture/records.jsonl').read_text().splitlines()[-80:];rows=[]
   for line in lines:
    try:
     x=json.loads(line);rows.append(dict(frame_id=x['frame_id'],capture_monotonic_ns=x['capture_monotonic_ns'],clock_id=x['clock_id'],boot_id=x['boot_id'],pred=x['candidate']['pred'],finite=x['candidate']['finite']))
    except (ValueError,KeyError):pass
   status['evidence_tail']=rows
  last=dict(status,acceptance_iteration=iteration,kind='SOFTWARE_BOOT_OBSERVATION_NOT_PHYSICAL_COLD_BOOT')
  (ROOT/'BOOT_ACCEPTANCE_LATEST.json').write_text(json.dumps(last,indent=2))
  try:
   body=json.dumps(last).encode();request=urllib.request.Request(base+'/receipt',data=body,headers={'Content-Type':'application/json'});urllib.request.urlopen(request,timeout=3).close()
  except Exception:pass
  time.sleep(10)
 subprocess.run(['systemctl','disable','rml24-boot-acceptance'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 if not last or not last.get('ready'):return 1
 return 0
if __name__=='__main__':sys.exit(main())
