"""Search the real RadioML2018.01A pulse: windowed-sinc lowpass vs RRC.

Primary metric = QPSK recall of the frozen model on clean generated signals.
Secondary = R[8] (real value 0.17) and -3dB/-20dB (real 0.0518 / 0.0713).
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


def windowed_sinc(fc, ntaps, window="hamming"):
    n = np.arange(ntaps) - (ntaps - 1) / 2.0
    h = 2.0 * fc * sinc(2.0 * fc * n)
    if window == "rect":
        w = np.ones(ntaps)
    elif window == "hamming":
        w = np.hamming(ntaps)
    elif window == "hann":
        w = np.hanning(ntaps)
    elif window == "blackman":
        w = np.blackman(ntaps)
    else:
        raise ValueError(window)
    h = h * w
    return h / np.sqrt(np.sum(h ** 2))


def rrc(sps, alpha, span):
    nt = span * sps + 1
    t = (np.arange(nt) - (nt - 1) / 2.0) / sps
    with np.errstate(divide="ignore", invalid="ignore"):
        num = np.sin(np.pi * t * (1 - alpha)) + 4 * alpha * t * np.cos(np.pi * t * (1 + alpha))
        den = np.pi * t * (1 - (4 * alpha * t) ** 2)
        h = num / den
        h[np.abs(t) < 1e-12] = 1 - alpha + 4 * alpha / np.pi
    return h / np.sqrt(np.sum(h ** 2))


def pulse_shape(symbols, h):
    up = np.zeros(len(symbols) * SPS, dtype=np.complex128)
    up[::SPS] = symbols
    x = np.convolve(up, h)
    d = (len(h) - 1) // 2
    return x[d:d + len(symbols) * SPS]


def gen_qpsk(h, nframes, base=0):
    const = np.exp(1j * 2 * np.pi * np.arange(4) / 4)
    out = np.zeros((nframes, N), dtype=np.complex128)
    for i in range(nframes):
        rng = np.random.default_rng(base + i)
        sym = const[rng.integers(0, 4, N // SPS)]
        out[i] = pulse_shape(sym, h)
        out[i] /= np.sqrt(np.mean(np.abs(out[i]) ** 2))
    return out


def metrics(x):
    M = len(x)
    R8 = np.real(np.sum(x[:, :N - 8] * np.conj(x[:, 8:])) / M / (N - 8))
    win = np.hanning(N)
    psd = np.mean(np.abs(np.fft.fftshift(np.fft.fft(x * win, axis=1), axes=1)) ** 2, axis=0)
    psd /= psd.sum() + 1e-12
    f = np.fft.fftshift(np.fft.fftfreq(N))
    pos = f >= 0
    ff, pp = f[pos], psd[pos]
    peak = pp.max()
    m3 = ff[pp >= peak * 0.501][-1]
    m20 = ff[pp >= peak * 0.01][-1]
    return R8, m3, m20


def main():
    ck = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    model = ADAMRV11Net(num_classes=24, **MODEL_KWARGS)
    model.load_state_dict(ck["model_state"])
    model.eval()

    def recall(x):
        xi = np.ascontiguousarray(np.stack([x.real, x.imag], axis=1)).astype(np.float32)
        with torch.inference_mode():
            out, _ = model(torch.from_numpy(xi))
        return float((out.numpy().argmax(axis=1) == 4).mean())

    rows = []
    print(f"{'pulse':<28} {'R8':>7} {'-3dB':>7} {'-20dB':>7} {'QPSK':>7}")
    for fc in [0.050, 0.055, 0.060, 0.0625, 0.065]:
        for w in ["rect", "hamming", "hann", "blackman"]:
            for nt in [33, 65, 129]:
                h = windowed_sinc(fc, nt, w)
                xg = gen_qpsk(h, 200, base=7000)
                r8, m3, m20 = metrics(xg)
                rec = recall(xg)
                name = f"wsinc_fc{fc}_t{nt}_{w}"
                rows.append((rec, name, r8, m3, m20))
                print(f"{name:<28} {r8:+.4f} {m3:.4f} {m20:.4f} {rec:.4f}")

    # a few RRC baselines
    for a in [0.1, 0.2, 0.3, 0.35]:
        for span in [3, 4, 8]:
            h = rrc(SPS, a, span)
            xg = gen_qpsk(h, 200, base=8000)
            r8, m3, m20 = metrics(xg)
            rec = recall(xg)
            name = f"rrc_a{a}_s{span}"
            rows.append((rec, name, r8, m3, m20))
            print(f"{name:<28} {r8:+.4f} {m3:.4f} {m20:.4f} {rec:.4f}")

    rows.sort(reverse=True)
    print("\nTOP 10 by QPSK recall:")
    for rec, name, r8, m3, m20 in rows[:10]:
        print(f"  {name:<28} QPSK={rec:.4f}  R8={r8:+.4f}  -3dB={m3:.4f} -20dB={m20:.4f}")

    out = Path(r"F:/嵌赛/fix10clean2a_results/PROBE_PULSE_SEARCH.json")
    out.write_text(json.dumps([{"name": n, "qpsk": r, "R8": a, "m3": b, "m20": c}
                               for r, n, a, b, c in rows], indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
