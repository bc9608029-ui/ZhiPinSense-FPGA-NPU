import pathlib,socket,json,hashlib,numpy as np,sys
root=pathlib.Path('/root/rml24_scan_execution_20261027');sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);sock.settimeout(20);sock.connect(str(root/'replay_npu.sock'));rows=[]
try:
 for f in sorted((root/'historical_replay_inputs').glob('*.bin')):
  b=f.read_bytes();a=np.frombuffer(b,dtype='<f4').reshape(8,2,1024);logits=[]
  for w in a:
   sock.sendall(w.tobytes());reply=b''
   while len(reply)<96:
    part=sock.recv(96-len(reply))
    if not part:raise RuntimeError('NPU closed')
    reply+=part
   logits.append(np.frombuffer(reply,dtype='<f4').copy())
  mean=np.asarray(logits).mean(axis=0,dtype=np.float64);rows.append({'seq':int(f.name.split('.')[0]),'input_sha256':hashlib.sha256(b).hexdigest(),'pred':int(np.argmax(mean)),'mean_logits':mean.tolist()})
finally:sock.close()
(root/'historical_npu_replay.json').write_text(json.dumps({'records':rows},indent=2));print('HISTORICAL_NPU_REPLAY_COMPLETE',len(rows))