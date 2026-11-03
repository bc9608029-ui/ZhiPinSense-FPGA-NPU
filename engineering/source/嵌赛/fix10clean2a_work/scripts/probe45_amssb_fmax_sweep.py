"""AM-SSB: sweep multitone audio bandwidth (fmax) to find the lowest inst-freq
that still keeps WC and SC recall >= 0.90.  Also measure SC sideband harmonics.
"""
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
N = c.SAMPLE_LENGTH; FS = c.SAMPLE_RATE_HZ
GOLD = r"F:\datasets\RadioML2018\GOLD_XYZ_OSC.0001_1024.hdf5"

def main():
    # --- measure SC sideband harmonics (compare WC) ---
    with h5py.File(GOLD, "r") as f:
        Y=f["Y"][:]; Z=f["Z"][:,0]; X=f["X"]
        for name in ["AM-SSB-WC","AM-SSB-SC"]:
            q=np.where((Z==30)&(Y[:,ORDER.index(name)]==1))[0][:400]
            xr=(X[q][:,:,0]+1j*X[q][:,:,1]).astype(np.complex128)
            dc=xr.mean(axis=1,keepdims=True); sb=xr-dc
            S=np.mean(np.abs(np.fft.fft(sb,axis=1))**2,axis=0)[:N//2]
            S=S/(S[1]+1e-12)
            bins=[round(float(S[i]),3) for i in range(1,9)]
            print(f"{name} sideband bins1-8: {bins}  sb/car={np.sqrt(np.mean(np.abs(sb)**2)/np.mean(np.abs(dc)**2)):.4f}")

    ck = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    model = ADAMRV11Net(num_classes=24, **MODEL_KWARGS)
    model.load_state_dict(ck["model_state"]); model.eval()

    def recall(fr, target):
        xi=np.ascontiguousarray(np.stack([fr.real,fr.imag],axis=1)).astype(np.float32)
        with torch.inference_mode(): out,_=model(torch.from_numpy(xi))
        pred=out.numpy().argmax(axis=1)
        return float((pred==target).mean())

    def instF(fr):
        ph=np.unwrap(np.angle(fr),axis=1)
        return float(np.diff(ph,axis=1).std()/(2*np.pi)*FS)

    def run(fmax, m, target, base=9_000_000, nf=500):
        fr=[]
        for i in range(nf):
            rng=np.random.default_rng(base+i)
            a=c._audio(rng,N,FS,fmax=fmax)
            z=a+1j*c._hilbert(a)
            x=(1.0+m*z)*np.exp(1j*c.CLEAN_PHASE)
            fr.append(c._scale_rms(x, c.TARGET_RMS[target]))
        fr=np.array(fr)
        return recall(fr, ORDER.index(target)), instF(fr)

    out={}
    print("\nfmax sweep (multitone 200..fmax):")
    for fmax in [500, 800, 1200, 1800, 2400, 3000]:
        rw, iw = run(fmax, 0.06, "AM-SSB-WC")
        rs, iss = run(fmax, 0.09, "AM-SSB-SC")
        out[f"fmax{fmax}"] = {"WC_rec":round(rw,3),"WC_instF":round(iw,1),
                              "SC_rec":round(rs,3),"SC_instF":round(iss,1)}
        print(f"  fmax={fmax:5d}: WC rec={rw:.3f} instF={iw:6.1f}   SC rec={rs:.3f} instF={iss:6.1f}")
    json.dump(out, open(r"F:/嵌赛/fix10clean2a_results/PROBE45_FMAX_SWEEP.json","w"), indent=1)

if __name__ == "__main__":
    main()
