"""Recall sweep for AM-DSB candidate structures against the frozen model."""
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
FS = c.SAMPLE_RATE_HZ
N = c.SAMPLE_LENGTH
FC = 6250.0
IDX = {name: i for i, name in enumerate(ORDER)}


def sawtooth(rng, phase=None):
    if phase is None:
        phase = rng.uniform(0, 1)
    n = np.arange(N)
    return 2.0 * ((n / N + phase) % 1.0) - 1.0   # ramp -1..+1, period N


def candidate(rng, kind, A, m):
    tt = np.arange(N) / FS
    sI = sawtooth(rng)
    sQ = sawtooth(rng)
    if kind == "complex_cos":       # complex envelope (indep I/Q audio), real carrier
        env = (A + m * (sI + 1j * sQ))
        x = env * np.cos(2 * np.pi * FC * tt)
    elif kind == "complex_analytic":  # complex envelope, analytic carrier
        env = (A + m * (sI + 1j * sQ))
        x = env * np.exp(1j * 2 * np.pi * FC * tt)
    elif kind == "real_cos":        # real audio, real carrier
        env = (A + m * sI)
        x = env * np.cos(2 * np.pi * FC * tt)
    elif kind == "real_analytic":   # real audio, analytic carrier
        env = (A + m * sI)
        x = env * np.exp(1j * 2 * np.pi * FC * tt)
    else:
        raise ValueError(kind)
    x = x * np.exp(1j * c.CLEAN_PHASE)
    return x / np.sqrt(np.mean(np.abs(x) ** 2) + 1e-12)


def main():
    ck = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    model = ADAMRV11Net(num_classes=24, **MODEL_KWARGS)
    model.load_state_dict(ck["model_state"])
    model.eval()

    def recall(gen, target, nframes=300, base=5_000_000):
        fr = np.stack([gen(np.random.default_rng(base + i)) for i in range(nframes)])
        xi = np.ascontiguousarray(np.stack([fr.real, fr.imag], axis=1)).astype(np.float32)
        with torch.inference_mode():
            out, _ = model(torch.from_numpy(xi))
        pred = out.numpy().argmax(axis=1)
        rec = float((pred == target).mean())
        cnt = Counter(pred.tolist())
        conf = ", ".join(f"{ORDER[k]}={v}" for k, v in sorted(cnt.items(), key=lambda kv: -kv[1])[:2])
        env = np.abs(fr)
        papr = 10 * np.log10((env ** 2).max() / (env ** 2).mean())
        return rec, papr, conf

    # measured references (400-frame): WC PAPR~5.08dB, SC~5.47dB; sideband/carrier WC~0.03 SC~0.05
    print("kind / A / m  ->  WC(idx19) & SC(idx20) recall, PAPR")
    for kind in ["complex_cos", "complex_analytic", "real_cos", "real_analytic"]:
        for A, m in [(1.0, 0.05), (1.0, 0.1), (1.0, 0.2), (1.0, 0.4), (1.0, 0.7), (1.0, 1.0),
                     (0.2, 0.2), (0.2, 0.5), (0.2, 1.0), (0.05, 0.5), (0.05, 1.0)]:
            r_wc, p_wc, _ = recall(lambda r, k=kind, A=A, m=m: candidate(r, k, A, m), IDX["AM-DSB-WC"])
            r_sc, p_sc, csc = recall(lambda r, k=kind, A=A, m=m: candidate(r, k, A, m), IDX["AM-DSB-SC"])
            print(f"{kind:16s} A={A:.2f} m={m:.2f}  WC rec={r_wc:.3f} papr={p_wc:.2f} | SC rec={r_sc:.3f} papr={p_sc:.2f} conf={csc}")


if __name__ == "__main__":
    main()
