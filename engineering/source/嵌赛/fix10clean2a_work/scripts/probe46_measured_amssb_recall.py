"""How well does the frozen model recognize the MEASURED AM-SSB (per SNR)?
This tells us the model's ceiling on real AM-SSB, and whether our clean recall
gap is a model limitation or a generator mismatch."""
from __future__ import annotations
import os, sys, json
from collections import Counter
import numpy as np, torch, h5py

USER_SITE = r"C:\Users\shado\AppData\Roaming\Python\Python313\site-packages"
if os.path.isdir(USER_SITE) and USER_SITE not in sys.path:
    sys.path.insert(0, USER_SITE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import radioml_clean_contract as c

MODEL_SRC = r"F:\FPGA_Work\sdr_amr_12class_ood_u_v1"
CHECKPOINT = (r"F:\FPGA_Work\sdr_rml24_npu_deployment_m29\_frozen\runs\rml24_base"
              r"\formal\t002_losscross_entropy_optadamw\seed2027\checkpoints\best.pt")
sys.path.insert(0, MODEL_SRC)
from models.ad_amr_v1_1_net import ADAMRV11Net
MODEL_KWARGS = {"denoiser_channels":24,"denoiser_blocks":3,"feature_channels":(32,48,64,96),
                "classifier_hidden":128,"dropout":0.15}
ORDER = c.LABEL_ORDER_24
GOLD = r"F:\datasets\RadioML2018\GOLD_XYZ_OSC.0001_1024.hdf5"

def main():
    ck = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    model = ADAMRV11Net(num_classes=24, **MODEL_KWARGS)
    model.load_state_dict(ck["model_state"]); model.eval()
    def recall(fr, target):
        xi=np.ascontiguousarray(np.stack([fr.real,fr.imag],axis=1)).astype(np.float32)
        with torch.inference_mode(): out,_=model(torch.from_numpy(xi))
        pred=out.numpy().argmax(axis=1)
        rec=float((pred==target).mean())
        cnt=Counter(pred.tolist())
        conf=", ".join(f"{ORDER[k]}={v}" for k,v in sorted(cnt.items(),key=lambda kv:-kv[1])[:2])
        return rec, conf
    out={}
    with h5py.File(GOLD,"r") as f:
        Y=f["Y"][:]; Z=f["Z"][:,0]; X=f["X"]
        for name in ["AM-SSB-WC","AM-SSB-SC","AM-DSB-WC","AM-DSB-SC","FM"]:
            ci=ORDER.index(name)
            print(f"\n=== measured {name} (500 frames) ===")
            for snr in [10, 14, 18, 20, 24, 28, 30]:
                q=np.where((Z==snr)&(Y[:,ci]==1))[0][:500]
                iq=(X[q][:,:,0]+1j*X[q][:,:,1]).astype(np.complex128)
                rec, conf = recall(iq, ci)
                out[f"{name}_snr{snr}"]=round(rec,3)
                print(f"  SNR{snr:2d}: recall={rec:.3f}  conf={conf}")
    json.dump(out, open(r"F:/嵌赛/fix10clean2a_results/PROBE46_MEASURED_AMSSB.json","w"), indent=1)

if __name__ == "__main__":
    main()
