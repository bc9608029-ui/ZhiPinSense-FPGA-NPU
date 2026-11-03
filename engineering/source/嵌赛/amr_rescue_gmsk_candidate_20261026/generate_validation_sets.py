import os,sys,json,hashlib,importlib.util
from pathlib import Path
import numpy as np
import torch
P=Path(__file__).resolve().parent
sys.path.insert(0,'E:/嵌赛/fix10class24_waveform_correct_v2_work/scripts')
import radioml_waveform_correct_v2 as gen
spec=importlib.util.spec_from_file_location('frozen_net','E:/FPGA_Work/sdr_amr_12class_ood_u_v1/models/ad_amr_v1_1_net.py');net=importlib.util.module_from_spec(spec);spec.loader.exec_module(net)
torch.set_num_threads(4)
model=net.ADAMRV11Net(num_classes=24,denoiser_channels=24,denoiser_blocks=3,feature_channels=(32,48,64,96),classifier_hidden=128,dropout=.15)
ck=torch.load('E:/FPGA_Work/24class_results/rml24_seed2027_best.pt',map_location='cpu',weights_only=True);model.load_state_dict(ck['model_state'],strict=True);model.eval()
for split,base,count in [('development',4100000,5),('validation',5100000,10)]:
 out=P/(split+'_seed'+str(base))
 out.mkdir(exist_ok=True);rows=[];tensors=[]
 for ci,name in enumerate(gen.GEN.LABEL_ORDER_24):
  for instance in range(count):
   seed=base+instance*100+ci;x=np.asarray(gen.generate_class_v2(name,seed));assert x.shape==(1024,) and np.isfinite(x).all()
   iq=np.stack([x.real,x.imag]).astype('<f4');data=iq.tobytes();file='%02d_%02d.bin'%(ci,instance);
   if (out/file).exists():
    assert (out/file).read_bytes()==data,'existing generated tensor changed'
   else:(out/file).write_bytes(data)
   peak=float(max(abs(x.real).max(),abs(x.imag).max())*68.46059377833956)
   if peak>2047:raise RuntimeError('actual TX numeric range exceeded '+file+': '+str(peak))
   rows.append(dict(class_index=ci,class_name=name,instance=instance,seed=seed,file=file,source_sha256=hashlib.sha256(data).hexdigest(),tx_component_peak=peak,above_original_1600_headroom=peak>1600));tensors.append(iq)
 inputs=np.stack(tensors);predictions={}
 for precision in ['fp32','bf16']:
  pred=[]
  with torch.inference_mode(),torch.autocast('cpu',dtype=torch.bfloat16,enabled=precision=='bf16'):
   for start in range(0,len(inputs),32):pred.extend(model(torch.from_numpy(inputs[start:start+32].copy()))[0].argmax(1).tolist())
  predictions[precision]=pred
 for i,r in enumerate(rows):r.update(host_fp32_pred=predictions['fp32'][i],host_bf16_pred=predictions['bf16'][i])
 np.random.default_rng(20261026).shuffle(rows)
 for seq,r in enumerate(rows):r['seq']=seq
 report=dict(kind='NEW_CLEAN_V2_MULTI_SEED_FIXED_PARAMETERS',split=split,seed_base=base,per_class=count,n=len(rows),fixed_scale=68.46059377833956,host_fp32_correct=sum(r['host_fp32_pred']==r['class_index'] for r in rows),host_bf16_correct=sum(r['host_bf16_pred']==r['class_index'] for r in rows),records=rows)
 (out/'expected_private.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(split,'n',len(rows),'host_fp32',report['host_fp32_correct'],'host_bf16',report['host_bf16_correct'],'max_peak',max(r['tx_component_peak'] for r in rows),flush=True)