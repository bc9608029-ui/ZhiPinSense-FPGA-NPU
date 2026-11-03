"""Decisive ASK diagnostic: what makes the model recognise OOK/4ASK/8ASK?

For each ASK class, measure real DC fraction (R_inf) and data-part spectrum,
then generate clean with 3 candidate pulses and report R_inf + recall.

Hypothesis: unipolar ASK is recognised by its DC line strength, which depends
on the pulse's DC gain sum(h) — NOT determined by the normalised autocorrelation
g[k].  RRC a=0.35 and wsinc may have different sum(h), hence different R_inf.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

USER_SITE = r"C:\Users\shado\AppData\Roaming\Python\Python313\site-packages"
if os.path.isdir(USER_SITE) and USER_SITE not in sys.path:
    sys.path.insert(0, USER_SITE)

import numpy as np  # noqa: E402
import h5py  # noqa: E402
import torch  # noqa: E402

GOLD = r"F:\datasets\RadioML2018\GOLD_XYZ_OSC.0001_1024.hdf5"
MODEL_SRC = r"F:\FPGA_Work\sdr_amr_12class_ood_u_v1"
CHECKPOINT = (r"F:\FPGA_Work\sdr_rml24_npu_deployment_m29\_frozen\runs\rml24_base"
              r"\formal\t002_losscross_entropy_optadamw\seed2027\checkpoints\best.pt")
sys.path.insert(0, MODEL_SRC)
from models.ad_amr_v1_1_net import ADAMRV11Net  # noqa: E402

MODEL_KWARGS = {"denoiser_channels": 24, "denoiser_blocks": 3,
                "feature_channels": (32, 48, 64, 96), "classifier_hidden": 128,
                "dropout": 0.15}
SPS = 8
N = 1024
CLEAN_PHASE = np.pi / 4.0
TARGET_RMS = {"OOK": 1.4714, "4ASK": 1.7525, "8ASK": 1.9116}
ORDER = ["OOK", "4ASK", "8ASK"]


def sinc(x):
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(np.abs(x) < 1e-12, 1.0, np.sin(np.pi * x) / (np.pi * x))


def wsinc(fc=0.059, ntaps=65):
    n = np.arange(ntaps) - (ntaps - 1) / 2.0
    h = 2.0 * fc * sinc(2.0 * fc * n)
    h = h * np.hanning(ntaps)
    return h / np.sqrt(np.sum(h ** 2))


def rrc(alpha=0.35, span=8):
    sps = SPS
    nt = span * sps + 1
    t = (np.arange(nt) - (nt - 1) / 2.0) / sps
    with np.errstate(divide="ignore", invalid="ignore"):
        num = np.sin(np.pi * t * (1 - alpha)) + 4 * alpha * t * np.cos(np.pi * t * (1 + alpha))
        den = np.pi * t * (1 - (4 * alpha * t) ** 2)
        h = num / den
        h[t == 0] = 1 - alpha + 4 * alpha / np.pi
    return h / np.sqrt(np.sum(h ** 2))


def pulse_shape(symbols, h):
    up = np.zeros(len(symbols) * SPS, dtype=np.complex128)
    up[::SPS] = symbols
    x = np.convolve(up, h)
    d = (len(h) - 1) // 2
    return x[d:d + len(symbols) * SPS]


def r_inf(x):
    M = len(x)
    R = np.zeros(64)
    for k in range(64):
        R[k] = np.real(np.sum(x[:, :N - k] * np.conj(x[:, k:])) / M / (N - k))
    R /= R[0]
    return R[60]


def main():
    ck = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    model = ADAMRV11Net(num_classes=24, **MODEL_KWARGS)
    model.load_state_dict(ck["model_state"])
    model.eval()

    def recall(x, idx):
        xi = np.ascontiguousarray(np.stack([x.real, x.imag], axis=1)).astype(np.float32)
        with torch.inference_mode():
            out, _ = model(torch.from_numpy(xi))
        return float((out.numpy().argmax(axis=1) == idx).mean())

    report = {}
    H_w = wsinc()
    H_r = rrc()
    print(f"sum(h): wsinc={H_w.sum():.3f}  rrc={H_r.sum():.3f}  (unit energy)")

    with h5py.File(GOLD, "r") as f:
        Y = f["Y"][:]
        Z = f["Z"][:, 0]
        for cidx, name in enumerate(ORDER):
            q = np.where((Z == 30) & (Y[:, cidx] == 1))[0][:300]
            real = (f["X"][q][:, :, 0] + 1j * f["X"][q][:, :, 1]).astype(np.complex128)
            rr = r_inf(real)
            print(f"\n{name}: real R_inf={rr:.4f}")
            report[name] = {"real_R_inf": round(float(rr), 4)}

            # generate with both pulses + a DC-adjusted wsinc
            m = int(name[0]) if name != "OOK" else 2
            levels = np.arange(m, dtype=np.float64)
            levels = levels / np.sqrt(np.mean(levels ** 2))  # unit RMS constellation

            for tag, h in [("wsinc", H_w), ("rrc", H_r)]:
                frames = np.zeros((200, N), dtype=np.complex128)
                for i in range(200):
                    rng = np.random.default_rng(5000 + i)
                    sym = levels[rng.integers(0, m, N // SPS)]
                    x = pulse_shape(sym, h) * np.exp(1j * CLEAN_PHASE)
                    x = x * (TARGET_RMS[name] / (np.sqrt(np.mean(np.abs(x) ** 2)) + 1e-12))
                    frames[i] = x
                ri = r_inf(frames)
                rec = recall(frames, cidx)
                print(f"  {tag:<6} R_inf={ri:.4f}  recall={rec:.4f}")
                report[name][tag] = {"R_inf": round(float(ri), 4), "recall": round(rec, 4)}

    Path(r"F:/嵌赛/fix10clean2a_results/PROBE3_ASK_DC.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")
    print("\n-> PROBE3_ASK_DC.json")


if __name__ == "__main__":
    main()
