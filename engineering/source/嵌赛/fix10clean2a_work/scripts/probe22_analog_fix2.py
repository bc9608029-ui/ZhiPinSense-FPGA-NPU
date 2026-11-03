"""Re-test analog fixes THROUGH the contract (correct TARGET_RMS) + confusion.

Monkeypatches the contract's _am_ssb / _am_dsb / _oqpsk with candidate fixes,
then uses c.generate_class (which applies _scale_rms to TARGET_RMS).
"""
from __future__ import annotations

import os
import sys
from collections import Counter
from pathlib import Path

USER_SITE = r"C:\Users\shado\AppData\Roaming\Python\Python313\site-packages"
if os.path.isdir(USER_SITE) and USER_SITE not in sys.path:
    sys.path.insert(0, USER_SITE)

import numpy as np  # noqa: E402
import torch  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import radioml_clean_contract as c  # noqa: E402

MODEL_SRC = r"F:\FPGA_Work\sdr_amr_12class_ood_u_v1"
CHECKPOINT = (r"F:\FPGA_Work\sdr_rml24_npu_deployment_m29\_frozen\runs\rml24_base"
              r"\formal\t002_losscross_entropy_optadamw\seed2027\checkpoints\best.pt")
sys.path.insert(0, MODEL_SRC)
from models.ad_amr_v1_1_net import ADAMRV11Net  # noqa: E402

MODEL_KWARGS = {"denoiser_channels": 24, "denoiser_blocks": 3,
                "feature_channels": (32, 48, 64, 96), "classifier_hidden": 128,
                "dropout": 0.15}
ORDER = c.LABEL_ORDER_24
FS = c.SAMPLE_RATE_HZ
N = c.SAMPLE_LENGTH


def am_ssb_dc(rng, carrier):
    a = c._audio(rng, N, FS)
    z = a + 1j * c._hilbert(a)
    m = 0.06 if carrier else 0.09
    x = (1.0 + m * z) * np.exp(1j * c.CLEAN_PHASE)
    return c._scale_rms(x, c.TARGET_RMS["AM-SSB-WC" if carrier else "AM-SSB-SC"])


def am_dsb_band(rng, carrier, f_c=4625.0):
    a = c._audio(rng, N, FS, fmax=1625.0)
    tt = np.arange(N) / FS
    if carrier:
        x = (1.0 + 0.8 * a) * np.exp(1j * 2 * np.pi * f_c * tt)
    else:
        x = a * np.exp(1j * 2 * np.pi * f_c * tt)
    return c._scale_rms(x, c.TARGET_RMS["AM-DSB-WC" if carrier else "AM-DSB-SC"])


def main():
    ck = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    model = ADAMRV11Net(num_classes=24, **MODEL_KWARGS)
    model.load_state_dict(ck["model_state"])
    model.eval()

    def predict(name, idx, nframes=500, base=1_100_000):
        fr = np.stack([c.generate_class(name, base + i) for i in range(nframes)])
        xi = np.ascontiguousarray(np.stack([fr.real, fr.imag], axis=1)).astype(np.float32)
        with torch.inference_mode():
            out, _ = model(torch.from_numpy(xi))
        pred = out.numpy().argmax(axis=1)
        rec = float((pred == idx).mean())
        cnt = Counter(pred.tolist())
        top = sorted(cnt.items(), key=lambda kv: -kv[1])[:3]
        conf = ", ".join(f"{ORDER[k]}={v}" for k, v in top)
        rms = float(np.sqrt(np.mean(np.abs(fr) ** 2)))
        return rec, conf, rms

    # AM-SSB DC carrier
    c._am_ssb = am_ssb_dc
    for name, idx in [("AM-SSB-WC", 17), ("AM-SSB-SC", 18)]:
        rec, conf, rms = predict(name, idx)
        print(f"{name:<10} DC-carrier: recall={rec:.3f} rms={rms:.2f}  conf={conf}")

    # AM-DSB bandpass
    c._am_dsb = am_dsb_band
    for name, idx in [("AM-DSB-WC", 19), ("AM-DSB-SC", 20)]:
        rec, conf, rms = predict(name, idx)
        print(f"{name:<10} band4625: recall={rec:.3f} rms={rms:.2f}  conf={conf}")


if __name__ == "__main__":
    main()
