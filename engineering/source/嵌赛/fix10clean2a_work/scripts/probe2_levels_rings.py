"""Corrected extraction: Gardner timing + wsinc matched filter.

For ASK (OOK/4ASK/8ASK): extract the actual symbol amplitude levels (I axis,
since they are real unipolar PAM before phase rotation) and the DC fraction.
For APSK (16/32/64/128): extract the |s| ring radii.

Then generate clean signals with the measured levels and check recall.
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
ORDER = ["OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
         "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
         "128QAM", "256QAM"]


def sinc(x):
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(np.abs(x) < 1e-12, 1.0, np.sin(np.pi * x) / (np.pi * x))


def wsinc(fc=0.059, ntaps=65, window="hann"):
    n = np.arange(ntaps) - (ntaps - 1) / 2.0
    h = 2.0 * fc * sinc(2.0 * fc * n)
    w = np.hanning(ntaps)
    h = h * w
    return h / np.sqrt(np.sum(h ** 2))


def gardner_offset(x):
    """Timing offset (0..sps-1) from |x|^2 cyclostationarity, summed over frames."""
    m = np.abs(x) ** 2
    nn = np.arange(N)
    C = np.sum(m * np.exp(-2j * np.pi * nn / SPS), axis=1)
    C = np.sum(C)  # coherent over frames (same fixed timing)
    d = int(round(-np.angle(C) * SPS / (2 * np.pi))) % SPS
    return d


def matched_symbols(x, h, off):
    """Matched-filter each frame, sample at offset `off`, return (Nframes, Nsym) complex."""
    d = (len(h) - 1) // 2
    out = []
    for fr in x:
        y = np.convolve(fr, h)[d:d + N]
        out.append(y[off::SPS])
    return np.array(out)


def levels_from(hist, edges, thresh_frac=0.03, merge_frac=0.05):
    centers = (edges[:-1] + edges[1:]) / 2
    peaks = centers[hist > hist.max() * thresh_frac]
    peaks = np.sort(peaks)
    scale = max(1.0, np.abs(peaks).max()) if len(peaks) else 1.0
    merged = []
    for p in peaks:
        if merged and abs(p - merged[-1]) < merge_frac * scale:
            merged[-1] = (merged[-1] + p) / 2
        else:
            merged.append(p)
    return np.round(np.array(merged), 3)


def main():
    H = wsinc()
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

    with h5py.File(GOLD, "r") as f:
        Y = f["Y"][:]
        Z = f["Z"][:, 0]
        X = f["X"]

        # ---- ASK: real levels (I axis) + DC fraction ----
        print("=== ASK: real symbol levels (matched filter, Gardner timing) ===")
        for cidx in [0, 1, 2]:
            q = np.where((Z == 30) & (Y[:, cidx] == 1))[0][:300]
            x = (X[q][:, :, 0] + 1j * X[q][:, :, 1]).astype(np.complex128)
            # un-rotate by the per-frame phase to recover the real PAM axis
            # phase = angle of mean of x (the DC points along the real axis)
            ph = np.angle(np.mean(x, axis=1))
            xr = (x * np.exp(-1j * ph[:, None])).real
            # matched filter on the REAL PAM signal
            d = (len(H) - 1) // 2
            y = np.array([np.convolve(r, H)[d:d + N] for r in xr])
            # timing from the complex |x|^2 (works for the real PAM axis too)
            off = gardner_offset(x)
            s = y[:, off::SPS].ravel()
            s = s / np.sqrt(np.mean(np.abs(s) ** 2))
            hist, edges = np.histogram(s, bins=80)
            lv = levels_from(hist, edges)
            R0 = np.mean(np.abs(x) ** 2)
            dc = np.mean(x, axis=1)
            print(f"{ORDER[cidx]:<5} levels(I)={lv}  R_inf={np.mean(np.abs(dc)**2)/R0:.4f}")
            report[f"{ORDER[cidx]}_levels"] = lv.tolist()

        # ---- APSK: ring radii ----
        print("\n=== APSK: ring radii (matched filter, Gardner timing) ===")
        for cidx in [9, 10, 11]:
            q = np.where((Z == 30) & (Y[:, cidx] == 1))[0][:300]
            x = (X[q][:, :, 0] + 1j * X[q][:, :, 1]).astype(np.complex128)
            off = gardner_offset(x)
            s = matched_symbols(x, H, off).ravel()
            s = s / np.sqrt(np.mean(np.abs(s) ** 2))
            r = np.abs(s)
            hist, edges = np.histogram(r, bins=100)
            radii = levels_from(hist, edges, thresh_frac=0.01, merge_frac=0.03)
            print(f"{ORDER[cidx]:<6} |s| rings = {radii}")
            report[f"{ORDER[cidx]}_rings"] = radii.tolist()

    Path(r"F:/嵌赛/fix10clean2a_results/PROBE2_LEVELS_RINGS.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")
    print("\n-> written PROBE2_LEVELS_RINGS.json")


if __name__ == "__main__":
    main()
