from pathlib import Path
import sys,numpy as np
from scipy.signal import resample_poly
sys.path.insert(0,'E:/FPGA_Work/rml24_repeat_agc_experiment_20261101')
from adaptive_repeat_recovery import recover_auto as recover_repeats

def recover_rate_and_repeats(raw,rx_fs=5120000):
 candidates=[]
 for down in (1,2,4):
  y=resample_poly(raw,1,down) if down!=1 else np.asarray(raw)
  try:
   x,meta=recover_repeats(y);quality=max(meta['head_reference_relative_error'],meta['tail_reference_relative_error']);candidates.append((quality,down,x,meta))
  except RuntimeError:pass
 if not candidates:raise RuntimeError('no supported public timing scale')
 quality,down,x,meta=min(candidates,key=lambda x:x[0]);meta=dict(meta,rx_fs_hz=float(rx_fs),detected_tx_logical_fs_hz=float(rx_fs/down),resample_down=float(down),cfo_physical_hz=float(meta['cfo_hz']*(rx_fs/down)/2560000));return x,meta
