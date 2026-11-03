"""Pin the exact RadioML2018.01A pulse by R[k]-shape match, then check all-class recall."""
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


def sinc(x):
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(np.abs(x) < 1e-12, 1.0, np.sin(np.pi * x) / (np.pi * x))


def wsinc(fc, ntaps, window):
    n = np.arange(ntaps) - (ntaps - 1) / 2.0
    h = 2.0 * fc * sinc(2.0 * fc * n)
    w = {"rect": np.ones(ntaps), "hamming": np.hamming(ntaps), "hann": np.hanning(ntaps),
         "blackman": np.blackman(ntaps), "kaiser_b5": np.kaiser(ntaps, 5.0),
         "kaiser_b8": np.kaiser(ntaps, 8.0), "kaiser_b12": np.kaiser(ntaps, 12.0)}[window]
    return (h * w) / np.sqrt(np.sum((h * w) ** 2))


def pulse_shape(symbols, h):
    up = np.zeros(len(symbols) * SPS, dtype=np.complex128)
    up[::SPS] = symbols
    x = np.convolve(up, h)
    d = (len(h) - 1) // 2
    return x[d:d + len(symbols) * SPS]


def Rvec(x, kmax=21):
    M = len(x)
    R = np.zeros(kmax)
    for k in range(kmax):
        R[k] = np.real(np.sum(x[:, :N - k] * np.conj(x[:, k:])) / M / (N - k))
    return R / R[0]


def main():
    with h5py.File(GOLD, "r") as f:
        X, Y, Z = f["X"], f["Y"], f["Z"]
        q = np.where((Z[:, 0] == 30) & (Y[:, 4] == 1))[0][:500]
        real = (X[q][:, :, 0] + 1j * X[q][:, :, 1]).astype(np.complex128)
    Rt = Rvec(real)
    print("real R[k] (k=0..15):", np.round(Rt[:16], 4))

    wins = ["rect", "hamming", "hann", "blackman", "kaiser_b5", "kaiser_b8", "kaiser_b12"]
    best = []
    for fc in np.arange(0.052, 0.070, 0.001):
        for w in wins:
            for nt in [33, 65, 129]:
                h = wsinc(fc, nt, w)
                sym = np.exp(1j * 2 * np.pi * np.arange(4) / 4)
                xg = gen(4, h, 40, base=1)
                Rc = Rvec(xg)
                rmse = np.sqrt(np.mean((Rc[:16] - Rt[:16]) ** 2))
                best.append((rmse, fc, w, nt))
    best.sort()
    print("\nTop 12 by R[k] RMSE (fc, window, taps):")
    for rmse, fc, w, nt in best[:12]:
        print(f"  fc={fc:.3f} {w:<10} t={nt:<3} rmse={rmse:.5f}")

    # full-class recall for the top candidates (distinct configs)
    ck = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    model = ADAMRV11Net(num_classes=24, **MODEL_KWARGS)
    model.load_state_dict(ck["model_state"])
    model.eval()

    def recall_cls(x, true_idx):
        xi = np.ascontiguousarray(np.stack([x.real, x.imag], axis=1)).astype(np.float32)
        with torch.inference_mode():
            out, _ = model(torch.from_numpy(xi))
        return float((out.numpy().argmax(axis=1) == true_idx).mean())

    # distinct top configs
    seen = set()
    cands = []
    for rmse, fc, w, nt in best:
        key = (round(fc, 3), w, nt)
        if key not in seen:
            seen.add(key)
            cands.append((fc, w, nt))
        if len(cands) >= 4:
            break

    # digital classes to check: idx -> (name, const order)
    import radioml_clean_contract as c  # noqa
    order = c.LABEL_ORDER_24
    results = {}
    for fc, w, nt in cands:
        h = wsinc(fc, nt, w)
        key = f"fc{fc:.3f}_{w}_t{nt}"
        recalls = {}
        for cidx in [3, 4, 5, 7, 8, 12, 15, 16]:  # BPSK QPSK 8PSK 32PSK 16APSK 16QAM 256QAM
            name = order[cidx]
            xg = gen_by_name(name, h, 100, base=5000)
            recalls[name] = recall_cls(xg, cidx)
        results[key] = recalls
        print(f"\n{key}: " + "  ".join(f"{k}={v:.2f}" for k, v in recalls.items()))

    Path(r"F:/嵌赛/fix10clean2a_results/PROBE_PULSE_MATCH.json").write_text(
        json.dumps({"top": [[round(r, 5), fc, w, nt] for r, fc, w, nt in best[:12]],
                    "recall": {k: v for k, v in results.items()}}, indent=2), encoding="utf-8")


# helper generators
def gen(mod, h, nf, base):
    const = np.exp(1j * 2 * np.pi * np.arange(mod) / mod)
    out = np.zeros((nf, N), dtype=np.complex128)
    for i in range(nf):
        rng = np.random.default_rng(base + i)
        out[i] = pulse_shape(const[rng.integers(0, mod, N // SPS)], h)
        out[i] /= np.sqrt(np.mean(np.abs(out[i]) ** 2))
    return out


def gen_by_name(name, h, nf, base):
    import radioml_clean_contract as c
    const = c._constellation(name)
    out = np.zeros((nf, N), dtype=np.complex128)
    for i in range(nf):
        rng = np.random.default_rng(base + i)
        sym = const[rng.integers(0, len(const), N // SPS)]
        x = pulse_shape(sym, h)
        if name in c.REAL_MODS:
            x = x * np.exp(1j * c.CLEAN_PHASE)
        out[i] = x / np.sqrt(np.mean(np.abs(x) ** 2))
    return out


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    main()
