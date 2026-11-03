"""Reproduce 16/32/64/128 APSK recall with wsinc + contract ring definitions.

Print per-class recall AND the confusion (top misclassifications) to see
what the model thinks each APSK signal is.
"""
from __future__ import annotations

import os
import sys

USER_SITE = r"C:\Users\shado\AppData\Roaming\Python\Python313\site-packages"
if os.path.isdir(USER_SITE) and USER_SITE not in sys.path:
    sys.path.insert(0, USER_SITE)

import numpy as np  # noqa: E402
import torch  # noqa: E402

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
ORDER = ["OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
         "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
         "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC", "AM-DSB-SC",
         "FM", "GMSK", "OQPSK"]


def sinc(x):
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(np.abs(x) < 1e-12, 1.0, np.sin(np.pi * x) / (np.pi * x))


def wsinc(fc=0.059, ntaps=65):
    n = np.arange(ntaps) - (ntaps - 1) / 2.0
    h = 2.0 * fc * sinc(2.0 * fc * n)
    h = h * np.hanning(ntaps)
    return h / np.sqrt(np.sum(h ** 2))


_H = wsinc()


def apsk_pts(rings):
    pts = []
    for count, radius in rings:
        off = np.random.default_rng(0).uniform(0, 2 * np.pi)
        for k in range(count):
            pts.append(radius * np.exp(1j * (2 * np.pi * k / count + off)))
    pts = np.array(pts)
    return pts / np.sqrt(np.mean(np.abs(pts) ** 2))


def pulse_shape(symbols):
    up = np.zeros(len(symbols) * SPS, dtype=np.complex128)
    up[::SPS] = symbols
    x = np.convolve(up, _H)
    d = (len(_H) - 1) // 2
    return x[d:d + len(symbols) * SPS]


RINGS = {
    16: [(4, 1.0), (12, 2.57)],
    32: [(4, 1.0), (12, 2.84), (16, 5.27)],
    64: [(4, 1.0), (12, 2.57), (20, 4.5), (28, 7.5)],
    128: [(4, 1.0), (12, 2.57), (20, 4.5), (28, 7.5), (36, 11.0), (28, 15.0)],
}


def main():
    ck = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    model = ADAMRV11Net(num_classes=24, **MODEL_KWARGS)
    model.load_state_dict(ck["model_state"])
    model.eval()

    for m in [16, 32, 64, 128]:
        idx = 8 + [16, 32, 64, 128].index(m)
        const = apsk_pts(RINGS[m])
        frames = np.zeros((400, N), dtype=np.complex128)
        for i in range(400):
            rng = np.random.default_rng(100000 + i)
            sym = const[rng.integers(0, len(const), N // SPS)]
            frames[i] = pulse_shape(sym)
        xi = np.ascontiguousarray(np.stack([frames.real, frames.imag], axis=1)).astype(np.float32)
        with torch.inference_mode():
            out, _ = model(torch.from_numpy(xi))
        pred = out.numpy().argmax(axis=1)
        rec = (pred == idx).mean()
        # confusion
        from collections import Counter
        cnt = Counter(pred.tolist())
        top = sorted(cnt.items(), key=lambda kv: -kv[1])[:4]
        print(f"{ORDER[idx]:<7} ({m}-APSK, idx {idx}): recall={rec:.3f}  top-preds=" +
              ", ".join(f"{ORDER[k]}={v}" for k, v in top))


if __name__ == "__main__":
    main()
