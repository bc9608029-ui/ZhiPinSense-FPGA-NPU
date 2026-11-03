import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import argparse,numpy as np
from common import write,sha

def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(exist_ok=False)
 t=np.arange(1024);tone=lambda k:512*np.exp(2j*np.pi*k*t/1024)
 rng=np.random.default_rng(20261030)
 vectors={'zero':np.zeros(1024),'dc':np.full(1024,512),
          'plus37':tone(37),'minus37':tone(-37),'edge511':tone(511),
          'dual':tone(37)+tone(-92),'random':rng.integers(-256,257,1024)+1j*rng.integers(-256,257,1024),
          'impulse':np.eye(1,1024,512).ravel()*1024}
 rows=[]
 for name,z in vectors.items():
  iq=np.stack([z.real,z.imag],axis=1).round().astype('<i2');path=a.out/(name+'.i16');iq.tofile(path)
  rows.append(dict(file=path.name,sha256=sha(path)))
 write(a.out/'manifest.json',dict(rows=rows,numpy_comparison='tolerance, NOT bit-exact FFT',
                                tolerance=dict(relative_l1=.02,peak_power_relative=.02)))
if __name__=='__main__':main()
