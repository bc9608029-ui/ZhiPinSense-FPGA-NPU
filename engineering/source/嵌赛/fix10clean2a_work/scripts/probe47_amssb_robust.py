"""AM-SSB fmax=800 robustness: recall over 2000 frames across 4 seed bases,
plus a fine fmax sweep 500-1100 to find the recall/instF tradeoff."""
from __future__ import annotations
import os, sys, json
from collections import Counter
import numpy as np, torch

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
ORDER = c.LABEL_ORDER_24; N=c.SAMPLE_LENGTH; FS=c.SAMPLE_RATE_HZ

def main():
    ck = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    model = ADAMRV11Net(num_classes=24, **MODEL_KWARGS)
    model.load_state_dict(ck["model_state"]); model.eval()
    def recall(fr, target):
        xi=np.ascontiguousarray(np.stack([fr.real,fr.imag],axis=1)).astype(np.float32)
        with torch.inference_mode(): out,_=model(torch.from_numpy(xi))
        return float((out.numpy().argmax(1)==target).mean())
    def instF(fr):
        ph=np.unwrap(np.angle(fr),axis=1); return float(np.diff(ph,axis=1).std()/(2*np.pi)*FS)
    def gen(fmax, m, target, base, nf):
        fr=[]
        for i in range(nf):
            rng=np.random.default_rng(base+i)
            a=c._audio(rng,N,FS,fmax=fmax)
            z=a+1j*c._hilbert(a)
            x=(1.0+m*z)*np.exp(1j*c.CLEAN_PHASE)
            fr.append(c._scale_rms(x, c.TARGET_RMS[target]))
        return np.array(fr)

    # fine fmax sweep
    print("fine fmax sweep (500 frames, single base):")
    for fmax in [500,600,700,800,900,1000,1100]:
        wc=gen(fmax,0.06,"AM-SSB-WC", 9_000_000, 500)
        sc=gen(fmax,0.09,"AM-SSB-SC", 9_000_000, 500)
        print(f"  fmax={fmax:5d}: WC rec={recall(wc,17):.3f} instF={instF(wc):6.1f} | SC rec={recall(sc,18):.3f} instF={instF(sc):6.1f}")

    # robustness: fmax=800 across 4 bases x 500 = 2000 frames
    print("\nfmax=800 robustness (4 bases x 500 = 2000 frames):")
    for fmax in [700, 800]:
        for target, m, ti in [("AM-SSB-WC",0.06,17), ("AM-SSB-SC",0.09,18)]:
            frs=[gen(fmax,m,target, 10_000_000 + b*1_000_000, 500) for b in range(4)]
            fr=np.concatenate(frs)
            print(f"  fmax={fmax} {target}: recall={recall(fr,ti):.3f} instF={instF(fr):.1f} (n=2000)")

if __name__ == "__main__":
    main()
