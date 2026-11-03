"""Probe the REAL RadioML2018.01A digital pulse shape.

Measures the pulse autocorrelation R[k], its power spectrum, and tests a family
of pulse-shape hypotheses by generating clean QPSK with each and measuring how
well the frozen model recognises it.

Writes: results/PROBE_REAL_PULSE.json
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

# digital classes share one pulse (indices in frozen order)
DIGITAL = [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]  # QPSK..256QAM


def rrc(sps, alpha, span):
    nt = span * sps + 1
    t = (np.arange(nt) - (nt - 1) / 2.0) / sps
    with np.errstate(divide="ignore", invalid="ignore"):
        num = np.sin(np.pi * t * (1 - alpha)) + 4 * alpha * t * np.cos(np.pi * t * (1 + alpha))
        den = np.pi * t * (1 - (4 * alpha * t) ** 2)
        h = num / den
        h[np.abs(t) < 1e-12] = 1 - alpha + 4 * alpha / np.pi
    return h / np.sqrt(np.sum(h ** 2))


def rc(sps, alpha, span):
    nt = span * sps + 1
    t = (np.arange(nt) - (nt - 1) / 2.0) / sps
    with np.errstate(divide="ignore", invalid="ignore"):
        h = np.sinc(t) * np.cos(np.pi * alpha * t) / (1 - (2 * alpha * t) ** 2)
        h[np.abs(t) < 1e-12] = 1.0
    return h / np.sqrt(np.sum(h ** 2))


def pulse_shape(symbols, h):
    up = np.zeros(len(symbols) * SPS, dtype=np.complex128)
    up[::SPS] = symbols
    x = np.convolve(up, h)
    d = (len(h) - 1) // 2
    return x[d:d + len(symbols) * SPS]


def autocorr(x):
    M = len(x)
    R = np.zeros(32)
    for k in range(32):
        R[k] = np.real(np.sum(x[:, :N - k] * np.conj(x[:, k:])) / M / (N - k))
    return R


def bw(x):
    # one-sided PSD via Hann-windowed FFT, return -3dB and -20dB fractional freq
    win = np.hanning(N)
    psd = np.mean(np.abs(np.fft.fftshift(np.fft.fft(x * win, axis=1), axes=1)) ** 2, axis=0)
    psd /= psd.sum() + 1e-12
    f = np.fft.fftshift(np.fft.fftfreq(N))
    pos = f >= 0
    pp = psd[pos]
    ff = f[pos]
    peak = pp.max()
    m3 = ff[pp >= peak * 0.501][-1]
    m20 = ff[pp >= peak * 0.01][-1]
    return m3, m20


def gen_qpsk(h, nframes, base=0):
    const = np.exp(1j * 2 * np.pi * np.arange(4) / 4)
    out = np.zeros((nframes, N), dtype=np.complex128)
    for i in range(nframes):
        rng = np.random.default_rng(base + i)
        sym = const[rng.integers(0, 4, N // SPS)]
        out[i] = pulse_shape(sym, h)
        out[i] /= np.sqrt(np.mean(np.abs(out[i]) ** 2))
    return out


def main():
    with h5py.File(GOLD, "r") as f:
        X, Y, Z = f["X"], f["Y"], f["Z"]
        idx = []
        for c in DIGITAL:
            q = np.where((Z[:, 0] == 30) & (Y[:, c] == 1))[0][:100]
            idx.extend(q)
        real = (X[idx][:, :, 0] + 1j * X[idx][:, :, 1]).astype(np.complex128)
    R = autocorr(real)
    m3r, m20r = bw(real)
    print("REAL digital pulse:")
    for k in range(16):
        print(f"  R[{k}] = {R[k]:+.4f}")
    print(f"  -3dB={m3r:.4f}  -20dB={m20r:.4f}")

    # spectral factorization -> symmetric (linear-phase) pulse from measured R
    L = 64
    Rc = np.concatenate([R[1:L + 1][::-1], R[:L + 1]])
    S = np.real(np.fft.fft(Rc))
    S = np.maximum(S, 0.0)
    P = np.sqrt(S)
    # linear-phase (symmetric) pulse: inverse of the (real) amplitude spectrum
    p_lin = np.real(np.fft.ifft(P))
    p_lin = np.roll(p_lin, (len(p_lin) - 1) // 2)  # centre at 0
    p_lin /= np.sqrt(np.sum(p_lin ** 2))

    # minimum-phase pulse via cepstrum
    logS = np.log(S + 1e-12)
    ceps = np.real(np.fft.ifft(logS))
    n = len(ceps)
    ceps_c = ceps.copy()
    ceps_c[1:n // 2] *= 2.0
    ceps_c[n // 2 + 1:] = 0.0
    p_min = np.real(np.fft.ifft(np.exp(np.fft.fft(ceps_c))))
    p_min /= np.sqrt(np.sum(p_min ** 2))

    # load model
    ck = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    model = ADAMRV11Net(num_classes=24, **MODEL_KWARGS)
    model.load_state_dict(ck["model_state"])
    model.eval()

    def recog(x):
        # x: (nframes,1024) complex -> model input [n,2,1024]
        xi = np.ascontiguousarray(np.stack([x.real, x.imag], axis=1)).astype(np.float32)
        with torch.inference_mode():
            out, _ = model(torch.from_numpy(xi))
        pred = out.numpy().argmax(axis=1)
        return float((pred == 4).mean())  # QPSK == index 4

    results = {"real": {"R": R.tolist(), "m3": m3r, "m20": m20r}}
    hyps = {}
    # hypothesis table
    hyps["rrc_a0.35_s8"] = rrc(SPS, 0.35, 8)
    hyps["rrc_a0.35_s3"] = rrc(SPS, 0.35, 3)
    hyps["rrc_a0.35_s2"] = rrc(SPS, 0.35, 2)
    hyps["rrc_a0.35_s1"] = rrc(SPS, 0.35, 1)
    hyps["rrc_a0.20_s8"] = rrc(SPS, 0.20, 8)
    hyps["rrc_a0.10_s8"] = rrc(SPS, 0.10, 8)
    hyps["rc_a0.35_s8"] = rc(SPS, 0.35, 8)
    hyps["rc_a0.35_s3"] = rc(SPS, 0.35, 3)
    hyps["spec_lin_129"] = p_lin
    hyps["spec_min_129"] = p_min

    print("\n{'hypothesis':<16} {'R8':>7} {'-3dB':>7} {'-20dB':>7} {'QPSK_rec':>9}")
    for name, h in hyps.items():
        xg = gen_qpsk(h, 200, base=5000)
        R8 = autocorr(xg)[8]
        m3, m20 = bw(xg)
        rec = recog(xg)
        results[name] = {"R8": float(R8), "m3": float(m3), "m20": float(m20),
                         "qpsk_recall": rec}
        print(f"{name:<16} {R8:+.4f} {m3:.4f} {m20:.4f} {rec:.4f}")

    out = Path(r"F:/嵌赛/fix10clean2a_results/PROBE_REAL_PULSE.json")
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print("\n->", out)


if __name__ == "__main__":
    main()
