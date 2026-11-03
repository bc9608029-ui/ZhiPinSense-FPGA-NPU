import os,sys,json,importlib.util
from pathlib import Path
import numpy as np
import torch
P=Path(__file__).resolve().parent
os.environ.setdefault('OMP_NUM_THREADS','4');torch.set_num_threads(4)
def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
net=module('frozen_net',Path('E:/FPGA_Work/sdr_amr_12class_ood_u_v1/models/ad_amr_v1_1_net.py'))
model=net.ADAMRV11Net(num_classes=24,denoiser_channels=24,denoiser_blocks=3,feature_channels=(32,48,64,96),classifier_hidden=128,dropout=.15)
ck=torch.load('E:/FPGA_Work/24class_results/rml24_seed2027_best.pt',map_location='cpu',weights_only=True)
model.load_state_dict(ck['model_state'],strict=True);model.eval()
y=np.load(P/'baseline_capture/0007.raw.npy')
iq=np.fromfile('E:/嵌赛/fix10class24_waveform_correct_v2_work/replay_out/layers/23.orig.tensor.bin',dtype='<f4').reshape(2,1024)
ref=iq[0]+1j*iq[1]
mods={'baseline':module('baseline','E:/AMR_Rescue_20261025/pilot_recovery.py'),'polar':module('polar',P/'candidate_polar.py'),'two_dc':module('two_dc',P/'candidate_two_dc.py')}
report={}
for name,m in mods.items():
 x,meta=m.recover(y);tensor=np.stack([x.real,x.imag],axis=1).astype('float32')
 predictions={}
 for precision in ['fp32','bf16']:
  with torch.inference_mode(),torch.autocast('cpu',dtype=torch.bfloat16,enabled=precision=='bf16'):
   logits=model(torch.from_numpy(tensor.copy()))[0].float()
  predictions[precision]={'predictions':logits.argmax(1).tolist(),'mean_pred':int(logits.mean(0).argmax()),'gmsk_minus_qam256_margin':(logits[:,22]-logits[:,16]).tolist()}
 alpha=np.sum(x*np.conj(ref),axis=1)/np.sum(abs(ref)**2)
 report[name]={'nrmse_by_window':(np.linalg.norm(x-ref,axis=1)/np.linalg.norm(ref)).tolist(),'amplitude_by_window':abs(alpha).tolist(),'phase_by_window_rad':np.angle(alpha).tolist(),'predictions':predictions,'metadata':meta}
 np.save(P/(name+'_gmsk_recovered.npy'),x)
 print(name,json.dumps(report[name]),flush=True)
(P/'offline_gmsk_two_dc.json').write_text(json.dumps(report,indent=2))