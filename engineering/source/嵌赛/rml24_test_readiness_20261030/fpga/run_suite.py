"""Eight-vector board test. Stop at first error; retain full expected count."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import argparse,subprocess,json
from common import read,write,sha,ROOT
def main():
 p=argparse.ArgumentParser();p.add_argument('--vectors',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
 p.add_argument('--backend',choices=['software','fpga','auto'],required=True);p.add_argument('--driver',type=Path)
 a=p.parse_args();a.out.mkdir(exist_ok=False);rows=read(a.vectors/'manifest.json')['rows'];results=[];rc=0
 for i,r in enumerate(rows):
  iq=a.vectors/r['file']
  if iq.resolve().parent!=a.vectors.resolve() or sha(iq)!=r['sha256']:raise ValueError('vector identity')
  cmd=[sys.executable,'-I',str(ROOT/'fpga/same_iq.py'),'--iq',str(iq),'--out',str(a.out/str(i)),
       '--backend',a.backend]
  if a.driver:cmd+=['--driver',str(a.driver)]
  result=subprocess.run(cmd,check=False,capture_output=True,text=True)
  (a.out/(str(i)+'.log')).write_text(result.stdout+result.stderr,encoding='utf8')
  detail=read(a.out/str(i)/'result.json') if (a.out/str(i)/'result.json').exists() else {}
  results.append(dict(file=r['file'],rc=result.returncode,result=detail))
  if result.returncode:rc=result.returncode;break
 write(a.out/'summary.json',dict(expected=len(rows),executed=len(results),passed=sum(r['rc']==0 for r in results),
                                results=results,complete=len(results)==len(rows),
                                device_used=a.backend!='software',production_receiver_integrated=False))
 print('SUITE expected=%d executed=%d passed=%d'%(len(rows),len(results),sum(r['rc']==0 for r in results)))
 return rc
if __name__=='__main__':sys.exit(main())
