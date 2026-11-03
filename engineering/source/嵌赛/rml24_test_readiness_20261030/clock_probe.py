"""PC pre/post-only SSH clock observation; no clock setting or RF control."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse,subprocess,time
from common import write

def main():
 p=argparse.ArgumentParser();p.add_argument('--host',required=True);p.add_argument('--out',type=Path,required=True)
 a=p.parse_args();samples=[]
 if a.out.exists():raise ValueError('fresh output required')
 for _ in range(7):
  t0=time.time_ns()
  result=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=5',a.host,
                         'python3 -c "import time; print(time.time_ns())"'],check=True,capture_output=True,text=True)
  t1=time.time_ns();board=int(result.stdout.strip())
  samples.append(dict(pc_before_ns=t0,pc_after_ns=t1,board_ns=board,lo_ns=board-t1,hi_ns=board-t0))
 lo=max(s['lo_ns'] for s in samples);hi=min(s['hi_ns'] for s in samples)
 if lo>hi or hi-lo>200_000_000:raise RuntimeError('clock offset unstable/uncertain; no RF scoring')
 write(a.out,dict(kind='BOARD_MINUS_PC_CLOCK_BOUND',lo_ns=lo,hi_ns=hi,samples=samples))
 print('OFFSET_BOUND_NS',lo,hi)
if __name__=='__main__':main()
