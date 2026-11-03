"""No hardware access. Validate package and optional target dependencies."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse,json,platform,shutil
from common import ROOT,IDENTITY,sha

def main():
 p=argparse.ArgumentParser();p.add_argument('--model-dir',type=Path);p.add_argument('--recovery',type=Path)
 p.add_argument('--radio',type=Path);p.add_argument('--npu-bin',type=Path);a=p.parse_args()
 for key,path in [('candidate_bit',ROOT/'fpga/smartscan_fix2_disable_icap.bit'),
                  ('rollback_bit',ROOT/'fpga/rollback_original.bit'),('radio',ROOT/'tx/vendor/pluto_link_probe.py')]:
  if sha(path)!=IDENTITY[key]:raise ValueError('identity mismatch '+key)
 if (ROOT/'SHA256SUMS.txt').exists():
  for line in (ROOT/'SHA256SUMS.txt').read_text(encoding='utf8').splitlines():
   h,name=line.split('  ',1)
   if sha(ROOT/name)!=h:raise ValueError('package member mismatch '+name)
 supplied=[a.model_dir,a.recovery,a.radio,a.npu_bin]
 if any(supplied) and not all(supplied):raise ValueError('all four board dependency paths required together')
 if all(supplied):
  for k,path in [('model_json',a.model_dir/'rml24_adamrv11_bf16.json'),('model_raw',a.model_dir/'rml24_adamrv11_bf16.raw'),
                 ('recovery',a.recovery),('radio',a.radio)]:
   if sha(path)!=IDENTITY[k]:raise ValueError('board dependency '+k)
  if not a.npu_bin.is_file():raise ValueError('missing NPU binary')
  import os
  if not os.access(a.npu_bin,os.X_OK):raise ValueError('NPU binary not executable')
 print(json.dumps(dict(package_identity='PASS',target_dependencies='PASS' if all(supplied) else 'NOT_CHECKED',
                      arch=platform.machine(),free_bytes=shutil.disk_usage(ROOT).free,
                      device_test_performed=False,rf_authorized_by_this_check=False)))
if __name__=='__main__':main()
