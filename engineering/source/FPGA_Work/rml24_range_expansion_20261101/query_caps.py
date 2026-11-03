import sys,json
from pathlib import Path
sys.path.insert(0,sys.argv[1]);import pluto_link_probe as l
out=[]
for uri in l.scan_usb():
 r=l.Radio(uri)
 try:
  d=dict(uri=uri)
  for name,ch in [('rx_lo',r.rlo),('tx_lo',r.tlo),('tx',r.tx),('rx',r.rx)]:
   for key in (['frequency_available'] if 'lo' in name else ['hardwaregain_available']):
    try:d[name+'_'+key]=r.get(ch,key)
    except Exception as e:d[name+'_'+key]=str(e)
  out.append(d)
 finally:l.destroy_context(r.ctx)
print(json.dumps(out))
