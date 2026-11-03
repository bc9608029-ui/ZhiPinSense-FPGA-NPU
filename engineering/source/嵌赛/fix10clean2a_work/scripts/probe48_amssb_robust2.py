"""Robust (3000-frame) recall vs instF for fmax in 1000..3000.  Find the lowest
fmax with WC recall comfortably >=0.95 and check the instF that results."""
from __future__ import annotations
import os, sys, json
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
ORDER=c.LABEL_ORDER_24; N=c.SAMPLE_LENGTH; FS=c.SAMPLE_RATE_HZ

def main():
    ck=torch.load(CHECKPOINT,map_location="cpu",weights_only=False)
    model=ADAMRV11Net(num_classes=24,**MODEL_KWARGS)
    model.load_state_dict(ck["model_state"]); model.eval()
    def recall(fr,t):
        xi=np.ascontiguousarray(np.stack([fr.real,fr.imag],1)).astype(np.float32)
        with torch.inference_mode(): out,_=model(torch.from_numpy(xi))
        return float((out.numpy().argmax(1)==t).mean())
    def instF(fr):
        ph=np.unwrap(np.angle(fr),axis=1); return float(np.diff(ph,axis=1).std()/(2*np.pi)*FS)
    def gen(fmax,m,target,bases,nf):
        fr=[]
        for b in bases:
            for i in range(nf):
                rng=np.random.default_rng(b+i)
                a=c._audio(rng,N,FS,fmax=fmax)
                z=a+1j*c._hilbert(a)
                x=(1.0+m*z)*np.exp(1j*c.CLEAN_PHASE)
                fr.append(c._scale_rms(x,c.TARGET_RMS[target]))
        return np.array(fr)
    bases=[10_000_000, 20_000_000, 30_000_000, 40_000_000, 50_000_000, 60_000_000]
    out={}
    print("robust (3000 frames) WC recall vs instF:")
    for fmax in [1000, 1200, 1400, 1600, 1800, 2000, 2400, 3000]:
        wc=gen(fmax,0.06,"AM-SSB-WC",bases,500)
        sc=gen(fmax,0.09,"AM-SSB-SC",bases,500)
        rw=recall(wc,17); rs=recall(sc,18)
        iw=instF(wc); iss=instF(sc)
        out[fmax]={"WC_rec":round(rw,4),"WC_instF":round(iw,1),"SC_rec":round(rs,4),"SC_instF":round(iss,1)}
        print(f"  fmax={fmax:5d}: WC rec={rw:.4f} instF={iw:6.1f} | SC rec={rs:.4f} instF={iss:6.1f}")
    json.dump(out, open(r"F:/嵌赛/fix10clean2a_results/PROBE48_ROBUST2.json","w"), indent=1)
if __name__=="__main__":
    main()
