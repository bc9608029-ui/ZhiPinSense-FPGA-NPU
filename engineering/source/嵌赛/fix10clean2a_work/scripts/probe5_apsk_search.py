"""Search 64APSK / 128APSK ring ratios that maximise frozen-model recall.

Ring COUNTS are fixed (DVB-S2X): 64=4+12+20+28, 128=4+12+20+28+36+28.
We search the radii (inner=1).  wsinc pulse, unit-RMS constellation, no phase
rotation (APSK is complex).  Recall over 160 frames per candidate.
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


def sinc(x):
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(np.abs(x) < 1e-12, 1.0, np.sin(np.pi * x) / (np.pi * x))


def wsinc(fc=0.059, ntaps=65):
    n = np.arange(ntaps) - (ntaps - 1) / 2.0
    h = 2.0 * fc * sinc(2.0 * fc * n)
    h = h * np.hanning(ntaps)
    return h / np.sqrt(np.sum(h ** 2))


_H = wsinc()


def apsk_const(rings):
    """rings: list of (count, radius). Returns unit-RMS complex constellation."""
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


def gen(const, nframes, base):
    out = np.zeros((nframes, N), dtype=np.complex128)
    for i in range(nframes):
        rng = np.random.default_rng(base + i)
        sym = const[rng.integers(0, len(const), N // SPS)]
        out[i] = pulse_shape(sym)
    return out


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

    # ---- 64APSK: rings 4+12+20+28, search r2,r3,r4 ----
    print("=== 64APSK (idx 10) ring search ===")
    best = []
    for r2 in [1.3, 1.6, 2.0, 2.4, 2.8]:
        for r3 in [1.9, 2.4, 3.0, 3.6, 4.2]:
            for r4 in [2.6, 3.2, 3.9, 4.6, 5.4]:
                rings = [(4, 1.0), (12, r2), (20, r3), (28, r4)]
                const = apsk_const(rings)
                x = gen(const, 160, base=100000)
                rec = recall(x, 10)
                best.append((rec, r2, r3, r4))
    best.sort(reverse=True)
    print("top 64APSK:")
    for rec, r2, r3, r4 in best[:10]:
        print(f"  r=({r2},{r3},{r4}) recall={rec:.3f}")

    # ---- 128APSK: rings 4+12+20+28+36+28, search r2..r6 ----
    print("\n=== 128APSK (idx 11) ring search ===")
    best2 = []
    for r2 in [1.3, 1.7, 2.1]:
        for r3 in [1.9, 2.6, 3.3]:
            for r4 in [2.6, 3.5, 4.5]:
                for r5 in [3.5, 4.7, 6.0]:
                    for r6 in [4.5, 6.0, 7.6]:
                        rings = [(4, 1.0), (12, r2), (20, r3), (28, r4), (36, r5), (28, r6)]
                        const = apsk_const(rings)
                        x = gen(const, 160, base=200000)
                        rec = recall(x, 11)
                        best2.append((rec, r2, r3, r4, r5, r6))
    best2.sort(reverse=True)
    print("top 128APSK:")
    for rec, r2, r3, r4, r5, r6 in best2[:10]:
        print(f"  r=({r2},{r3},{r4},{r5},{r6}) recall={rec:.3f}")

    Path(r"F:/嵌赛/fix10clean2a_results/PROBE5_APSK_SEARCH.json").write_text(
        json.dumps({"64": [[round(r, 3), *r2v] for r, *r2v in best[:10]],
                    "128": [[round(r, 3), *r2v] for r, *r2v in best2[:10]]}, indent=2),
        encoding="utf-8")


if __name__ == "__main__":
    main()
