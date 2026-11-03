"""Sweep OQPSK I/Q offset (shared bits, wsinc pulse) to find the offset that
matches the real cross-correlation (+11) and maximizes recall."""
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
H = c.wsinc_taps()


def pulse(symbols, h):
    up = np.zeros(len(symbols) * SPS)
    up[::SPS] = symbols
    x = np.convolve(up, h)
    d = (len(h) - 1) // 2
    return x[d:d + len(symbols) * SPS]


def oqpsk_shared(rng, offset):
    bits = 2.0 * rng.integers(0, 2, size=NS) - 1.0
    i = pulse(bits, H)
    n = len(i)
    q = np.zeros_like(i)
    if offset >= 0:
        q[offset:] = i[:n - offset]   # Q[n] = I[n - offset] (Q delayed by offset)
    else:
        off = -offset
        q[:n - off] = i[off:]         # Q[n] = I[n + off] (Q advanced by off)
    x = i + 1j * q
    return x / np.sqrt(np.mean(np.abs(x) ** 2) + 1e-12)


def main():
    ck = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    model = ADAMRV11Net(num_classes=24, **MODEL_KWARGS)
    model.load_state_dict(ck["model_state"])
    model.eval()

    # self-check cross-corr argmax for one offset
    x = oqpsk_shared(np.random.default_rng(0), 4)
    I, Q = x.real, x.imag
    xc = np.correlate(I, Q, mode="full")[len(I) - 1 - 16:len(I) - 1 + 17]
    print(f"self-check offset=4 (Q delayed 4): argmax lag = {np.argmax(np.abs(xc)) - 16}")
    x = oqpsk_shared(np.random.default_rng(0), -11)
    I, Q = x.real, x.imag
    xc = np.correlate(I, Q, mode="full")[len(I) - 1 - 16:len(I) - 1 + 17]
    print(f"self-check offset=-11 (Q advanced 11): argmax lag = {np.argmax(np.abs(xc)) - 16}\n")

    def recall(offset, nframes=500, base=3_000_000):
        fr = np.stack([oqpsk_shared(np.random.default_rng(base + i), offset) for i in range(nframes)])
        xi = np.ascontiguousarray(np.stack([fr.real, fr.imag], axis=1)).astype(np.float32)
        with torch.inference_mode():
            out, _ = model(torch.from_numpy(xi))
        pred = out.numpy().argmax(axis=1)
        rec = float((pred == 23).mean())
        cnt = Counter(pred.tolist())
        conf = ", ".join(f"{ORDER[k]}={v}" for k, v in sorted(cnt.items(), key=lambda kv: -kv[1])[:2])
        env = np.abs(fr)
        inst = np.diff(np.unwrap(np.angle(fr), axis=1), axis=1) / (2 * np.pi / c.SAMPLE_RATE_HZ)
        return rec, conf, env.min(), np.std(inst)

    print("real: env_min=0.001 inst_std=14654 PAPR=5.23")
    for offset in [0, 2, 4, 8, 11, 12, -2, -4, -8, -11, -12]:
        rec, conf, emin, istd = recall(offset)
        print(f"offset={offset:>3}  rec={rec:.3f}  env_min={emin:.3f}  inst_std={istd:.0f}  conf={conf}")


if __name__ == "__main__":
    main()
