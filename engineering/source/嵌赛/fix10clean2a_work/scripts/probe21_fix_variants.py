"""Test candidate fixes for the 5 broken classes (OQPSK, AM-SSB x2, AM-DSB x2).

Each candidate is a full clean generator function; recall is measured against
the frozen model (500 frames/class).  Also prints env_min to confirm structure.
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
SPS = c.SPS
H = c.wsinc_taps()


def rrc_taps(alpha, span=8, sps=SPS):
    nsym = span
    k = np.arange(-nsym * sps / 2, nsym * sps / 2 + 1) / sps
    # RRC impulse response
    h = np.zeros_like(k)
    for i, t in enumerate(k):
        if abs(t) < 1e-9:
            h[i] = 1 - alpha + 4 * alpha / np.pi
        elif abs(abs(t) - 1 / (4 * alpha)) < 1e-9:
            h[i] = (alpha / np.sqrt(2)) * ((1 + 2 / np.pi) * np.sin(np.pi / (4 * alpha))
                                          + (1 - 2 / np.pi) * np.cos(np.pi / (4 * alpha)))
        else:
            h[i] = (np.sin(np.pi * t * (1 - alpha)) + 4 * alpha * t * np.cos(np.pi * t * (1 + alpha))) \
                   / (np.pi * t * (1 - (4 * alpha * t) ** 2))
    return h / np.sqrt(np.sum(h ** 2))


def half_sine_taps(sps=SPS):
    # half-sine pulse, length = 1 symbol (sps samples)
    h = np.sin(np.pi * np.arange(sps) / sps)
    return h / np.sqrt(np.sum(h ** 2))


def pulse(symbols, h):
    up = np.zeros(len(symbols) * SPS)
    up[::SPS] = symbols
    x = np.convolve(up, h)
    d = (len(h) - 1) // 2
    return x[d:d + len(symbols) * SPS]


def oqpsk_gen(rng, h, delay=True):
    bits = 2.0 * rng.integers(0, 2, size=2 * c.N_SYMBOLS) - 1.0
    i = bits[0::2]
    q = bits[1::2]
    xi = pulse(i, h)
    xq = pulse(q, h)
    if delay:
        d = SPS // 2
        xqd = np.zeros_like(xq)
        xqd[d:] = xq[:-d]
        xq = xqd
    x = xi + 1j * xq
    return x / np.sqrt(np.mean(np.abs(x) ** 2) + 1e-12)


def am_ssb_dc(rng, carrier):
    a = c._audio(rng, N, FS)
    z = a + 1j * c._hilbert(a)          # analytic (single sideband)
    m = 0.06 if carrier else 0.09
    x = (1.0 + m * z) * np.exp(1j * c.CLEAN_PHASE)
    return x / np.sqrt(np.mean(np.abs(x) ** 2) + 1e-12)


def am_dsb_band(rng, carrier, f_c=4625.0):
    a = c._audio(rng, N, FS, fmax=1625.0)   # baseband audio [200,1625]
    tt = np.arange(N) / FS
    if carrier:
        x = (1.0 + 0.8 * a) * np.exp(1j * 2 * np.pi * f_c * tt)
    else:
        x = a * np.exp(1j * 2 * np.pi * f_c * tt)
    return x / np.sqrt(np.mean(np.abs(x) ** 2) + 1e-12)


def main():
    ck = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    model = ADAMRV11Net(num_classes=24, **MODEL_KWARGS)
    model.load_state_dict(ck["model_state"])
    model.eval()

    def recall(gen, idx, nframes=500, base=1_000_000):
        fr = np.stack([gen(np.random.default_rng(base + i)) for i in range(nframes)])
        xi = np.ascontiguousarray(np.stack([fr.real, fr.imag], axis=1)).astype(np.float32)
        with torch.inference_mode():
            out, _ = model(torch.from_numpy(xi))
        return float((out.numpy().argmax(axis=1) == idx).mean()), float(np.abs(fr).min())

    print("=== OQPSK variants ===")
    for label, h, delay in [("wsinc+delay", H, True), ("wsinc-nodelay", H, False),
                            ("halfsine+delay", half_sine_taps(), True),
                            ("rrc035+delay", rrc_taps(0.35), True),
                            ("rrc02+delay", rrc_taps(0.2), True)]:
        rec, emin = recall(lambda r, h=h, d=delay: oqpsk_gen(r, h, d), 23)
        print(f"  {label:<16} recall={rec:.3f}  env_min={emin:.3f}")

    print("\n=== AM-SSB variants ===")
    rec, emin = recall(lambda r: am_ssb_dc(r, True), 17)
    print(f"  DC-carrier WC       recall={rec:.3f}  env_min={emin:.3f}")
    rec, emin = recall(lambda r: am_ssb_dc(r, False), 18)
    print(f"  DC-carrier SC       recall={rec:.3f}  env_min={emin:.3f}")

    print("\n=== AM-DSB variants ===")
    rec, emin = recall(lambda r: am_dsb_band(r, True), 19)
    print(f"  band 4625 WC (m=0.8) recall={rec:.3f}  env_min={emin:.3f}")
    rec, emin = recall(lambda r: am_dsb_band(r, False), 20)
    print(f"  band 4625 SC        recall={rec:.3f}  env_min={emin:.3f}")


if __name__ == "__main__":
    main()
