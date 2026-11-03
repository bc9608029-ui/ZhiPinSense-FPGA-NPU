import sys,subprocess,socket,time,struct,json,importlib.util
import numpy as np
from pathlib import Path
root=Path(sys.argv[1]);root.mkdir();log=(root/'worker.log').open('w');sock=root/'worker.sock';model='/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16/'
p=subprocess.Popen(['/root/rml24_fpga_shared_owner_20261031/build/npu_stream_shared',model+'rml24_adamrv11_bf16.json',model+'rml24_adamrv11_bf16.raw',str(sock)],stdout=log,stderr=subprocess.STDOUT)
s=None;rows=[];frames=0;reference=None;error=None
sys.path.insert(0,'/root/rml24_test_setup_w1QsCF/rml24_test_readiness_20261030/fpga');from same_iq import compare
names=['zero','dc','plus37','minus37','edge511','dual','random','impulse']
def exact(n):
 b=b''
 while len(b)<n:
  a=s.recv(n-len(b));assert a,'worker EOF';b+=a
 return b
try:
 for _ in range(300):
  if sock.exists():break
  assert p.poll() is None;time.sleep(.1)
 s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);s.settimeout(20);s.connect(str(sock))
 for i in range(16):
  for _ in range(8):
   s.sendall(bytes(8192));v=np.frombuffer(exact(96),dtype='<f4').copy();assert np.isfinite(v).all()
   if reference is None:reference=v
   assert np.array_equal(v,reference),'NPU changed after PSD';frames+=1
  name=names[i%8];data=Path('/root/rml24_manual_fpga_1793380256/vectors/'+name+'.i16').read_bytes();assert len(data)==4096
  request=struct.pack('<IIII',0x7fc05350,0x31505344,0,0)+data+bytes(8192-16-4096);s.sendall(request);raw=exact(8192);a=np.frombuffer(raw,dtype='<u8').copy();a.tofile(root/(str(i)+'.u64'));metrics=compare(np.frombuffer(data,dtype='<i2').reshape(1024,2),a);rows.append(dict(index=i,name=name,comparison=metrics));assert metrics['pass_'],'PSD comparison failed'
 # Verify NPU after final PSD as well.
 for _ in range(8):
  s.sendall(bytes(8192));v=np.frombuffer(exact(96),dtype='<f4');assert np.array_equal(v,reference);frames+=1
except Exception as e:error=repr(e)
finally:
 if s:s.close()
 try:p.wait(timeout=30)
 except subprocess.TimeoutExpired:error=(error or '')+' worker did not stop; no force kill'
 log.close()
out=dict(expected_psd=16,executed_psd=len(rows),passed_psd=sum(x['comparison']['pass_'] for x in rows),npu_frames=frames,expected_npu_frames=136,error=error,worker_rc=p.poll(),rows=rows);(root/'SUMMARY.json').write_text(json.dumps(out,indent=2));print(json.dumps(out));print('REAL_IQ_MATRIX_DONE',flush=True)
