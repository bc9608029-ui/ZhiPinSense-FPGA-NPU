from pathlib import Path
import json,numpy as np,subprocess,socket,time,hashlib,sys
base=Path(__file__).parent;plan=json.loads((base/'COMPARE_PLAN_PUBLIC.json').read_text());capture=Path(plan['board_capture']);out=Path('/root/rml24_clean_compare_'+str(int(time.time())));out.mkdir()
worker=Path('/root/amr_rescue_20261025/build/npu_stream');assert hashlib.sha256(worker.read_bytes()).hexdigest()=='cc88cb0bf5cde766937d011978314b7dafd1122d0f18e1cbda731ec2f7a440d8'
model=Path('/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16');assert hashlib.sha256((model/'rml24_adamrv11_bf16.raw').read_bytes()).hexdigest()=='c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151'
state=subprocess.check_output(['systemctl','is-active','rml24-receiver'],universal_newlines=True).strip() if subprocess.run(['systemctl','is-active','--quiet','rml24-receiver']).returncode==0 else subprocess.check_output(['systemctl','show','rml24-receiver','-p','ActiveState','--value'],universal_newlines=True).strip()
restore=state in ('active','activating');subprocess.run(['systemctl','stop','rml24-receiver'],check=True)
assert subprocess.run(['pgrep','-x','npu_stream'],stdout=subprocess.PIPE).returncode!=0
p=None;conn=None;log=None;results=[];clean=False
try:
 log=(out/'npu.log').open('w');p=subprocess.Popen([sys.executable,'/root/rml24_fpga_ui_20261031/delivery_guard_persistent/scripts/hardware_restart_guard.py','--state-dir','/var/lib/rml24-fpga-shared-guard',str(worker),str(model/'rml24_adamrv11_bf16.json'),str(model/'rml24_adamrv11_bf16.raw'),str(out/'npu.sock')],stdout=log,stderr=subprocess.STDOUT)
 deadline=time.monotonic()+30
 while not (out/'npu.sock').exists():
  assert p.poll() is None and time.monotonic()<deadline;time.sleep(.1)
 conn=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);conn.settimeout(10);conn.connect(str(out/'npu.sock'))
 def infer(tensor):
  logits=[]
  for window in np.asarray(tensor,dtype='<f4'):
   assert window.shape==(2,1024) and np.isfinite(window).all();conn.sendall(window.tobytes());data=b''
   while len(data)<96:
    block=conn.recv(96-len(data));assert block;data+=block
   logits.append(np.frombuffer(data,dtype='<f4').copy())
  mean=np.mean(logits,axis=0,dtype=np.float64);return dict(pred=int(mean.argmax()),logits=mean.tolist())
 for record in plan['records']:
  raw=(base/record['reference']).read_bytes();assert hashlib.sha256(raw).hexdigest()==record['sha'];x=np.frombuffer(raw,dtype='<f4').reshape(2,1024);reference=x[0]+1j*x[1];clean_result=infer(np.repeat(x[None],8,axis=0));frames=[]
  for frame_id in record['frame_ids']:
   t=np.fromfile(capture/('%06d.inputs.bin'%frame_id),dtype='<f4').reshape(8,2,1024);z=(t[:,0,:]+1j*t[:,1,:]).mean(axis=0);design=np.column_stack([reference,np.ones(1024)]);coef=np.linalg.lstsq(design,z,rcond=None)[0];error=np.linalg.norm(z-design@coef)/max(np.linalg.norm(z-z.mean()),1e-12);frames.append(dict(frame_id=frame_id,inference=infer(t),relative_fit_error=float(error),gain=float(abs(coef[0])),phase=float(np.angle(coef[0])),dc=float(abs(coef[1])),rms=float(np.sqrt(np.mean(abs(z)**2)))))
  results.append(dict(index=record['index'],source_sha=record['sha'],clean_inference=clean_result,frames=frames))
 conn.close();conn=None;assert p.wait(timeout=30)==0;clean=True
 (out/'RESULT.json').write_text(json.dumps(dict(results=results,guard_clean=True,model_changed=False),indent=2));print('COMPARE_RESULT_ROOT='+str(out),flush=True)
finally:
 if conn:conn.close()
 if p and p.poll() is None:
  try:p.wait(timeout=30)
  except subprocess.TimeoutExpired:pass
 if log:log.close()
 if restore and p and p.poll()==0 and not Path('/var/lib/rml24-fpga-shared-guard/reset_required.json').exists():subprocess.run(['systemctl','start','rml24-receiver'],check=True)
