"""Reconstruct the real RadioML2018.01A digital pulse via spectral factorization.

The signal x[n] = sum_i a_i p[n - i*sps] (IID symbols) has autocorrelation
R[k] = g[k] = pulse autocorrelation.  Its power spectrum is G(f) = |P(f)|^2.
So the linear-phase pulse is p = IFFT(sqrt(FFT(g_sym))).  We then test whether
clean QPSK/16QAM/8PSK generated with this measured pulse is recognised.

Writes: results/PROBE_REAL_PULSE2.json
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
DIGITAL = [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]


def autocorr(x, kmax=160):
    M = len(x)
    R = np.zeros(kmax)
    for k in range(kmax):
        R[k] = np.real(np.sum(x[:, :N - k] * np.conj(x[:, k:])) / M / (N - k))
    return R


def bw_from_R(R, kmax):
    # power spectrum from symmetric autocorrelation
    g_sym = np.concatenate([R[1:kmax][::-1], R[:kmax]])
    G = np.real(np.fft.fft(g_sym))
    G = np.maximum(G, 0.0)
    f = np.fft.fftfreq(len(G)) * 2  # FFT of autocorr has resolution 1/(2kmax-1)... approx
    pos = f >= 0
    ff = f[pos]
    pp = G[pos]
    peak = pp.max()
    m3 = ff[pp >= peak * 0.501][-1]
    m20 = ff[pp >= peak * 0.01][-1]
    return m3, m20


def linear_phase_pulse(R, kmax=128):
    g_sym = np.concatenate([R[1:kmax][::-1], R[:kmax]])
    G = np.real(np.fft.fft(g_sym))
    G = np.maximum(G, 0.0)
    p = np.real(np.fft.ifft(np.sqrt(G)))
    # p is length 2*kmax-1, symmetric, centred at (len-1)//2
    p /= np.sqrt(np.sum(p ** 2))
    return p


def pulse_shape(symbols, h):
    up = np.zeros(len(symbols) * SPS, dtype=np.complex128)
    up[::SPS] = symbols
    x = np.convolve(up, h)
    d = (len(h) - 1) // 2
    return x[d:d + len(symbols) * SPS]


def gen(mod, h, nframes, base=0):
    const = np.exp(1j * 2 * np.pi * np.arange(mod) / mod) if mod in (4, 8, 16, 32) else None
    out = np.zeros((nframes, N), dtype=np.complex128)
    for i in range(nframes):
        rng = np.random.default_rng(base + i)
        sym = const[rng.integers(0, mod, N // SPS)]
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

    R = autocorr(real, kmax=160)
    print("real R[k], k=0..16:", np.round(R[:17], 4))

    # measured bandwidth directly from signal
    win = np.hanning(N)
    psd = np.mean(np.abs(np.fft.fftshift(np.fft.fft(real * win, axis=1), axes=1)) ** 2, axis=0)
    psd /= psd.sum() + 1e-12
    f = np.fft.fftshift(np.fft.fftfreq(N))
    pos = f >= 0
    ff, pp = f[pos], psd[pos]
    peak = pp.max()
    print(f"real -3dB={ff[pp >= peak*0.501][-1]:.4f}  -20dB={ff[pp >= peak*0.01][-1]:.4f}")

    ck = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    model = ADAMRV11Net(num_classes=24, **MODEL_KWARGS)
    model.load_state_dict(ck["model_state"])
    model.eval()

    def recog(x, true_idx):
        xi = np.ascontiguousarray(np.stack([x.real, x.imag], axis=1)).astype(np.float32)
        with torch.inference_mode():
            out, _ = model(torch.from_numpy(xi))
        return float((out.numpy().argmax(axis=1) == true_idx).mean())

    results = {}
    for kmax in [64, 128, 256]:
        p = linear_phase_pulse(R, kmax=kmax)
        # truncate to central taps that hold 99.95% energy
        c = np.abs(p) ** 2
        tot = c.sum()
        for half in range(8, len(p) // 2 + 1):
            cen = c[len(p) // 2 - half:len(p) // 2 + half + 1].sum()
            if cen / tot >= 0.9995:
                break
        p_trunc = p[len(p) // 2 - half:len(p) // 2 + half + 1]
        xq = gen(4, p_trunc, 200, base=9000)
        rec = recog(xq, 4)
        m3, m20 = bw_from_R(autocorr(xq), 64)
        results[f"spec_lin_k{kmax}_taps{len(p_trunc)}"] = {"qpsk_recall": rec, "m3": m3, "m20": m20}
        print(f"kmax={kmax} taps={len(p_trunc)}: QPSK_rec={rec:.4f} -3dB={m3:.4f} -20dB={m20:.4f}")

    # print the pulse shape for kmax=128
    p = linear_phase_pulse(R, kmax=128)
    c = p[len(p) // 2 - 20:len(p) // 2 + 21]
    print("\npulse centre 41 taps:", np.round(c, 4))

    out = Path(r"F:/嵌赛/fix10clean2a_results/PROBE_REAL_PULSE2.json")
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print("\n->", out)


if __name__ == "__main__":
    main()
