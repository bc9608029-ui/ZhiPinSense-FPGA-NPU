"""Read-only handover audit. No training or device writes. Outputs exploratory metrics."""
import csv, hashlib, importlib.util, json
from pathlib import Path
import numpy as np
import torch

ROOT = Path('E:/')
WORK = ROOT / '嵌赛/fix10class24_realrf_finetune_pilot1_work'
OUT = Path(__file__).resolve().parent
torch.set_num_threads(4)
source = ROOT / 'FPGA_Work/sdr_amr_12class_ood_u_v1/models/ad_amr_v1_1_net.py'
spec = importlib.util.spec_from_file_location('handover_model', source)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
ckpt = ROOT / 'FPGA_Work/24class_results/rml24_seed2027_best.pt'
digest = hashlib.sha256(ckpt.read_bytes()).hexdigest()
assert digest == '96cd25f87d6f6f8cacda94432136db9420f74300cecba71df3c9fbe49817be6d'
ck = torch.load(ckpt, map_location='cpu', weights_only=True)
model = mod.ADAMRV11Net(num_classes=24, denoiser_channels=24,
    denoiser_blocks=3, feature_channels=(32,48,64,96), classifier_hidden=128, dropout=.15)
model.load_state_dict(ck['model_state'], strict=True)
model.eval()
truth = {r['source_id']:r for r in csv.DictReader(
    (WORK/'line_a/results/source_manifest_960.tsv').open(encoding='utf-8'), delimiter='\t')}

def predict(x):
    with torch.inference_mode():
        return np.concatenate([model(torch.from_numpy(x[i:i+32].copy()))[0].argmax(1).numpy()
                               for i in range(0,len(x),32)])

report = {'status':'EXPLORATORY_OFFLINE_NOT_FINAL_TEST', 'checkpoint_sha256':digest,
          'precision':'host_fp32', 'sessions':{}}
for session in ['S1','S2']:
    folder = next((WORK/'board_captures/extracted_S1_S2_20261022').glob('pilot1_capture_'+session+'_*'))
    rows = list(csv.DictReader((folder/('capture_results_'+session+'.tsv')).open(encoding='utf-8'),delimiter='\t'))
    src=[]; rx=[]; labels=[]; board=[]
    for r in rows:
        sid=r['source_id']; data=(folder/(sid+'.model_input.bin')).read_bytes()
        assert hashlib.sha256(data).hexdigest()==r['model_input_sha256']
        raw=(WORK/'line_a/inputs'/session/(sid+'.bin')).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==truth[sid]['source_iq_sha256']
        rx.append(np.frombuffer(data,dtype='<f4').reshape(2,1024))
        src.append(np.frombuffer(raw,dtype='<f4').reshape(2,1024))
        labels.append(int(truth[sid]['class_index']));board.append(int(r['board_pred1']))
    src=np.stack(src);rx=np.stack(rx);labels=np.array(labels)
    assert len(rx)==240 and np.isfinite(rx).all()
    rms=lambda x:np.sqrt(np.mean(np.sum(x*x,axis=1),axis=1))
    # Fixed transforms use no source IQ or class labels; diagnostic only.
    centered=rx-rx.mean(axis=2,keepdims=True)
    variants={'source':src,'rx':rx,'rx_remove_mean':centered,
              'rx_iq_swap':rx[:,::-1,:].copy(),
              'rx_conjugate':rx*np.array([1,-1],dtype=np.float32)[None,:,None]}
    result={'n':len(rx),'hashes_verified':len(rx)*2,
            'gate_pass':sum(r['gate_pass']=='1' for r in rows),
            'board_forced_accuracy':float(np.mean(np.array(board)==labels)),
            'source_rms_median':float(np.median(rms(src))),
            'rx_rms_median':float(np.median(rms(rx))),
            'rx_dc_energy_fraction_median':float(np.median(np.sum(rx.mean(2)**2,axis=1)/(rms(rx)**2))),
            'variants':{}}
    for name,x in variants.items():
        pred=predict(x.astype(np.float32));result['variants'][name]={
            'correct':int(np.sum(pred==labels)),'accuracy':float(np.mean(pred==labels)),
            'per_class_recall':[float(np.mean(pred[labels==c]==c)) for c in range(24)]}
        if name=='rx':result['host_board_prediction_agreement']=float(np.mean(pred==np.array(board)))
    report['sessions'][session]=result
    print(session,json.dumps({k:v for k,v in result.items() if k!='variants'}),flush=True)
    print({k:v['correct'] for k,v in result['variants'].items()},flush=True)
(OUT/'audit_iq_results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
