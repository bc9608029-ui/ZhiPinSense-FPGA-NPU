"""AM-SSB: does LOW-FREQ audio (195 Hz + harmonics, matching measured sideband)
still give recall >= 0.90 at the correct m (0.06 WC / 0.09 SC)?

probe43 only swept m>=0.2, which is WRONG m for WC (real m=0.06).  This probe
tests the correct m with the low-frequency audio that matches the measured
sideband harmonic structure (bins 1..16 = 1.0/.294/.162/.110/...).
"""
from __future__ import annotations
import os, sys, json
from collections import Counter

USER_SITE = r"C:\Users\shado\AppData\Roaming\Python\Python313\site-packages"
if os.path.isdir(USER_SITE) and USER_SITE not in sys.path:
    sys.path.insert(0, USER_SITE)
import numpy as np
import torch
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import radioml_clean_contract as c

MODEL_SRC = r"F:\FPGA_Work\sdr_amr_12class_ood_u_v1"
CHECKPOINT = (r"F:\FPGA_Work\sdr_rml24_npu_deployment_m29\_frozen\runs\rml24_base"
              r"\formal\t002_losscross_entropy_optadamw\seed2027\checkpoints\best.pt")
sys.path.insert(0, MODEL_SRC)
from models.ad_amr_v1_1_net import ADAMRV11Net

MODEL_KWARGS = {"denoiser_channels": 24, "denoiser_blocks": 3,
                "feature_channels": (32, 48, 64, 96), "classifier_hidden": 128,
                "dropout": 0.15}
ORDER = c.LABEL_ORDER_24
N = c.SAMPLE_LENGTH
FS = c.SAMPLE_RATE_HZ

# measured sideband harmonic amplitudes (bin1..16, relative to bin1=1.0)
BINS = [1.0, 0.294, 0.162, 0.110, 0.065, 0.060, 0.039, 0.036,
        0.026, 0.022, 0.015, 0.016, 0.009, 0.008, 0.007, 0.005]


def sine(rng, f=FS/N):
    ph = rng.uniform(0, 2*np.pi)
    tt = np.arange(N)/FS
    return np.sqrt(2)*np.sin(2*np.pi*f*tt + ph)


def sawtooth(rng):
    ph = rng.uniform(0, 1)
    n = np.arange(N)
    return 2.0*((n/N + ph) % 1.0) - 1.0


def matched(rng, nharm):
    """Sum of cosines at k*(Fs/N) with measured harmonic amplitudes."""
    ph = rng.uniform(0, 2*np.pi)
    n = np.arange(N)
    f0 = FS/N
    a = np.zeros(N)
    for k in range(1, nharm+1):
        a += BINS[k-1]*np.cos(2*np.pi*f0*k*n/FS + ph*(k+1))
    return a/(np.sqrt(np.mean(a**2))+1e-12)


def main():
    ck = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    model = ADAMRV11Net(num_classes=24, **MODEL_KWARGS)
    model.load_state_dict(ck["model_state"])
    model.eval()

    def recall(fr, target):
        xi = np.ascontiguousarray(np.stack([fr.real, fr.imag], axis=1)).astype(np.float32)
        with torch.inference_mode():
            out, _ = model(torch.from_numpy(xi))
        pred = out.numpy().argmax(axis=1)
        rec = float((pred == target).mean())
        cnt = Counter(pred.tolist())
        conf = ", ".join(f"{ORDER[k]}={v}" for k, v in sorted(cnt.items(), key=lambda kv:-kv[1])[:2])
        return rec, conf

    def inst_std(fr):
        ph = np.unwrap(np.angle(fr), axis=1)
        return float(np.diff(ph, axis=1).std()/(2*np.pi)*FS)

    def run(audio_fn, m, target, base=8_000_000, nf=500):
        fr = []
        for i in range(nf):
            rng = np.random.default_rng(base+i)
            a = audio_fn(rng)
            z = a + 1j*c._hilbert(a)
            x = (1.0 + m*z)*np.exp(1j*c.CLEAN_PHASE)
            fr.append(c._scale_rms(x, c.TARGET_RMS[target]))
        fr = np.array(fr)
        rec, conf = recall(fr, ORDER.index(target))
        return rec, conf, inst_std(fr)

    out = {"measured_ref": "WC instF32.7 SC instF32.8 @SNR30; WC sideband/carrier0.052 SC0.0875"}
    for audio_name, fn in [("sine195", sine), ("sawtooth195", sawtooth),
                           ("matched5", lambda r: matched(r, 5)),
                           ("matched16", lambda r: matched(r, 16))]:
        for target, m in [("AM-SSB-WC", 0.06), ("AM-SSB-SC", 0.09)]:
            rec, conf, istd = run(fn, m, target)
            key = f"{audio_name}_{target}"
            out[key] = {"m": m, "recall": rec, "instF": round(istd,1), "conf": conf}
            print(f"{audio_name:11s} {target:10s} m={m:.2f}: recall={rec:.3f} instF={istd:.1f}Hz  {conf}")

    # current contract (multi-tone) reference
    for target, m in [("AM-SSB-WC", 0.06), ("AM-SSB-SC", 0.09)]:
        def mt(rng):
            return c._audio(rng, N, FS)
        rec, conf, istd = run(mt, m, target)
        out[f"multitone_{target}"] = {"m": m, "recall": rec, "instF": round(istd,1), "conf": conf}
        print(f"{'multitone':11s} {target:10s} m={m:.2f}: recall={rec:.3f} instF={istd:.1f}Hz  {conf}")

    json.dump(out, open(r"F:/嵌赛/fix10clean2a_results/PROBE44_AMSSB_LOWFREQ.json","w"), indent=1)

if __name__ == "__main__":
    main()
