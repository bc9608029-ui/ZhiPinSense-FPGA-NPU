"""Isolated software/fpga/auto PSD diagnostic. Not installed into production RX."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import argparse,json,subprocess,time
import numpy as np
from common import load,ROOT,write,sha
gold=load('frozen_scan_golden',ROOT/'fpga/smart_scan_golden.py')

def compare(iq,actual):
 expected=gold.spectrum(iq)['power_u54'].astype(np.float64)
 if actual.shape!=(1024,) or np.any(actual>>54):raise ValueError('invalid u54 spectrum')
 power=actual.astype(np.float64)
 if expected.max()==0:return dict(pass_=bool(np.all(actual==0)),relative_l1=0.0 if not actual.any() else 1.0,peak_ok=bool(not actual.any()))
 relative=float(np.abs(power-expected).sum()/expected.sum())
 # Tied peaks: allow any numerical maximum within 1% of maximum reference.
 peak=int(power.argmax());peak_ok=bool(expected[peak]>=.99*expected.max())
 amplitude=float(abs(power.max()-expected.max())/expected.max())
 return dict(pass_=relative<=.02 and amplitude<=.02 and peak_ok,relative_l1=relative,
             peak_power_relative_error=amplitude,peak_ok=peak_ok,peak_bin=peak)

def main():
 p=argparse.ArgumentParser();p.add_argument('--iq',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
 p.add_argument('--backend',choices=['software','fpga','auto'],required=True)
 p.add_argument('--driver',type=Path);a=p.parse_args()
 if a.iq.stat().st_size!=4096:raise ValueError('exact 1024 complex LE-int16 required')
 iq=np.fromfile(a.iq,dtype='<i2').reshape(1024,2);a.out.mkdir(exist_ok=False)
 sw=gold.spectrum(iq)['power_u54'].astype('<u8');sw.tofile(a.out/'software.u64')
 record=dict(iq_sha256=sha(a.iq),requested=a.backend,backend_used='software',ok=True,fallback_reason=None)
 rc=0
 if a.backend!='software':
  if not a.driver:raise ValueError('explicit driver required')
  tick=time.perf_counter();executed=False
  try:
   r=subprocess.run([str(a.driver.resolve()),'--execute',str(a.iq.resolve()),
                     str((a.out/'fpga.u64').resolve()),str((a.out/'fpga.json').resolve())],
                     capture_output=True,text=True,check=False)
   executed=True
   # No subprocess timeout: killing a live DDR owner is unsafe. The driver owns its deadline.
   (a.out/'driver.log').write_text(r.stdout+r.stderr,encoding='utf8')
   record.update(driver_rc=r.returncode,elapsed_seconds=time.perf_counter()-tick)
   if r.returncode:
    record['fallback_reason']='driver_exit_'+str(r.returncode)
    record['requires_board_reset']=r.returncode==3
    if a.backend=='fpga' or r.returncode==3:record['ok']=False;rc=r.returncode or 1
   else:
    actual=np.fromfile(a.out/'fpga.u64',dtype='<u8');metrics=compare(iq,actual)
    record.update(backend_used='fpga',comparison=metrics,ok=metrics['pass_'])
    if not metrics['pass_']:rc=1
  except OSError as e:
   record['fallback_reason']=('driver_output_invalid: ' if executed else 'driver_launch_failed: ')+str(e)
   if executed or a.backend=='fpga':record['ok']=False;rc=1
 # auto uses software only on an idle hardware/launch failure; never hides a successful but incorrect FPGA result.
 write(a.out/'result.json',record);print(json.dumps(record));return rc
if __name__=='__main__':raise SystemExit(main())
