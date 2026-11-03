#!/usr/bin/env python3
"""Production entry candidate. Not installed; promotion receipt required."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,uuid,shutil,time
from evidence_retention import prune_completed
from boot_recovery import prepare_hardware_start
ROOT=Path(__file__).resolve().parent
MARKER=Path('/var/lib/rml24-fpga-shared-guard/reset_required.json')
def main():
 receipt=json.loads((ROOT/'PROMOTED_RELEASE.json').read_text())
 if not receipt.get('all_promotion_gates_passed'):raise RuntimeError('release not promoted')
 for filename,digest in receipt['files'].items():
  p=Path(filename) if Path(filename).is_absolute() else ROOT/filename
  if hashlib.sha256(p.read_bytes()).hexdigest()!=digest:raise RuntimeError('release identity mismatch '+filename)
 # Wait for platform nodes and the one RX Pluto before opening any NPU Device.
 sys.path.insert(0,'/root/amr_rescue_20261025')
 import pluto_link_probe as link
 ready=False
 for attempt in range(120):
  uris=link.scan_usb()
  if len(uris)>1:print('AMBIGUOUS_RX_PLUTO; no hardware started',flush=True);return 78
  if len(uris)==1 and Path('/dev/udmabuf0').exists() and Path('/dev/mem').exists():ready=True;break
  time.sleep(.5)
 if not ready:print('USB_OR_DISPLAY_NOT_READY; no NPU Device opened',flush=True);return 1
 try:print('BOOT_HARDWARE_START '+json.dumps(prepare_hardware_start(receipt)),flush=True)
 except Exception as exc:print('HARDWARE_START_BLOCKED '+str(exc),flush=True);return 78
 # Fresh short socket path; retained history is separate from per-run evidence.
 logs=Path('/var/log/rml24-integrated');logs.mkdir(parents=True,exist_ok=True)
 print('EVIDENCE_RETENTION '+json.dumps(prune_completed(logs,keep=1)),flush=True)
 if shutil.disk_usage(logs).free<1024**3:print('DISK_SPACE_REQUIRED; no hardware started',flush=True);return 78
 history=Path('/var/lib/rml24-integrated/history.txt');history.parent.mkdir(parents=True,exist_ok=True)
 run=logs/('r'+uuid.uuid4().hex[:12])
 cmd=[sys.executable,str(ROOT/'scripts/run_candidate_finalize_v2.py'),'--legacy-root','/root/amr_rescue_20261025','--model-dir','/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16','--npu-sha','cc88cb0bf5cde766937d011978314b7dafd1122d0f18e1cbda731ec2f7a440d8','--run',str(run),'--mode','FIXED','--duration-sec','86400','--history-file',str(history)]
 # exec retains systemd signal supervision. Supervisor owns UI/RX/guard lifecycle.
 os.execv(sys.executable,[sys.executable]+cmd[1:])
if __name__=='__main__':sys.exit(main())
