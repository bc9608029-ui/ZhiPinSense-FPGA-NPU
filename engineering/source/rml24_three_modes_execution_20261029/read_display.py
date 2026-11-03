import mmap,os,io,base64,numpy as np
from PIL import Image
fd=os.open('/dev/mem',os.O_RDONLY|os.O_SYNC)
try:
 mm=mmap.mmap(fd,1843200*2,flags=mmap.MAP_SHARED,prot=mmap.PROT_READ,offset=0x30100000)
 result=Image.new('RGB',(1280,1440))
 for i in range(2):
  a=np.frombuffer(mm[i*1843200:(i+1)*1843200],dtype='<u2').reshape(720,1280).astype(np.uint32)
  rgb=np.stack([((a>>11)&31)*255//31,((a>>5)&63)*255//63,(a&31)*255//31],axis=-1).astype(np.uint8)
  result.paste(Image.fromarray(rgb),(0,i*720))
 mm.close();b=io.BytesIO();result.save(b,format='PNG');print('EVIDENCE_BEGIN');print(base64.b64encode(b.getvalue()).decode());print('EVIDENCE_END')
finally:os.close(fd)
