"""Test OQPSK as Q=I-delayed-by-8 (full symbol, shared bits) with rectangular pulse.

Self-checks the I-Q cross-correlation signature, then measures recall.
"""
from __future__ import annotations

import os
import sys
from collections import Counter

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
SPS = c.SPS
NS = c.N_SYMBOLS


def rect_pulse(n=SPS):
    h = np.ones(n)
    return h / np.sqrt(np.sum(h ** 2))


def halfsine(n=SPS):
    h = np.sin(np.pi * np.arange(n) / n)
    return h / np.sqrt(np.sum(h ** 2))


def pulse(symbols, h):
    up = np.zeros(len(symbols) * SPS)
    up[::SPS] = symbols
    x = np.convolve(up, h)
    d = (len(h) - 1) // 2
    return x[d:d + len(symbols) * SPS]


def oqpsk_shared(rng, h, delay):
    """I and Q share the same bit stream; Q = I delayed by `delay` samples."""
    bits = 2.0 * rng.integers(0, 2, size=NS) - 1.0
    i = pulse(bits, h)
    q = np.zeros_like(i)
    if delay > 0:
        q[delay:] = i[:-delay]
    elif delay < 0:
        q[:delay] = i[-delay:]
    else:
        q = i
    x = i + 1j * q
    return x / np.sqrt(np.mean(np.abs(x) ** 2) + 1e-12)


def oqpsk_indep(rng, h, delay):
    """Independent bits for I and Q, Q offset by delay."""
    bits = 2.0 * rng.integers(0, 2, size=2 * NS) - 1.0
    i = pulse(bits[0::2], h)
    q = pulse(bits[1::2], h)
    if delay > 0:
        qd = np.zeros_like(q); qd[delay:] = q[:-delay]; q = qd
    elif delay < 0:
        qd = np.zeros_like(q); qd[:delay] = q[-delay:]; q = qd
    return i + 1j * q


def main():
    ck = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    model = ADAMRV11Net(num_classes=24, **MODEL_KWARGS)
    model.load_state_dict(ck["model_state"])
    model.eval()

    # self-check cross-corr signature of the hypothesis Q = I delayed by 8
    rng = np.random.default_rng(0)
    h = rect_pulse()
    x = oqpsk_shared(rng, h, 8)
    I, Q = x.real, x.imag
    xc = np.correlate(I, Q, mode="full")[len(I) - 1 - SPS: len(I) - 1 + SPS + 1]
    xc /= np.max(np.abs(xc))
    print("self-check xc (Q=I-delayed-8, rect pulse), lag -8..+8:")
    print("  " + " ".join(f"{v:+.2f}" for v in xc[::2]))
    print(f"  argmax lag = {np.argmax(np.abs(xc)) - SPS}\n")

    def recall(gen, nframes=500, base=2_000_000):
        fr = np.stack([gen(np.random.default_rng(base + i)) for i in range(nframes)])
        xi = np.ascontiguousarray(np.stack([fr.real, fr.imag], axis=1)).astype(np.float32)
        with torch.inference_mode():
            out, _ = model(torch.from_numpy(xi))
        pred = out.numpy().argmax(axis=1)
        rec = float((pred == 23).mean())
        cnt = Counter(pred.tolist())
        conf = ", ".join(f"{ORDER[k]}={v}" for k, v in sorted(cnt.items(), key=lambda kv: -kv[1])[:3])
        env = np.abs(fr)
        inst = np.diff(np.unwrap(np.angle(fr), axis=1), axis=1) / (2 * np.pi / c.SAMPLE_RATE_HZ)
        papr = 10 * np.log10((env ** 2).max() / (env ** 2).mean())
        return rec, conf, env.min(), np.std(inst), papr

    print("real target: env_min=0.001 inst_freq_std=14654 PAPR=5.23")
    variants = [
        ("rect, shared, delay8", rect_pulse(), 8, True),
        ("rect, shared, delay4", rect_pulse(), 4, True),
        ("rect, shared, delay-8", rect_pulse(), -8, True),
        ("rect, indep, delay4", rect_pulse(), 4, False),
        ("rect, indep, delay0", rect_pulse(), 0, False),
        ("halfsine, shared, delay8", halfsine(), 8, True),
        ("halfsine, shared, delay4", halfsine(), 4, True),
    ]
    for label, h, delay, shared in variants:
        gen = (lambda r, h=h, d=delay, s=shared: oqpsk_shared(r, h, d) if s else oqpsk_indep(r, h, d))
        rec, conf, emin, istd, papr = recall(gen)
        print(f"{label:<24} rec={rec:.3f} env_min={emin:.3f} inst_std={istd:.0f} PAPR={papr:.2f}  conf={conf}")


if __name__ == "__main__":
    main()
