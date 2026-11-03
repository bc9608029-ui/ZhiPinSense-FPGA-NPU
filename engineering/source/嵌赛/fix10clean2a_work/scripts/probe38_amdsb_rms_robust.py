"""Measure native RMS of AM classes + robust recall test for AM-DSB candidate."""
from __future__ import annotations

import os
import sys
from collections import Counter

USER_SITE = r"C:\Users\shado\AppData\Roaming\Python\Python313\site-packages"
if os.path.isdir(USER_SITE) and USER_SITE not in sys.path:
    sys.path.insert(0, USER_SITE)

import numpy as np  # noqa: E402
import torch  # noqa: E402
import h5py  # noqa: E402

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
GOLD = r"F:\datasets\RadioML2018\GOLD_XYZ_OSC.0001_1024.hdf5"


def sawtooth(rng, phase=None):
    if phase is None:
        phase = rng.uniform(0, 1)
    n = np.arange(N)
    return 2.0 * ((n / N + phase) % 1.0) - 1.0


def candidate(rng, m):
    s = sawtooth(rng)
    tt = np.arange(N) / FS
    x = (1.0 + m * s) * np.cos(2 * np.pi * FC * tt) * np.exp(1j * c.CLEAN_PHASE)
    return x / np.sqrt(np.mean(np.abs(x) ** 2) + 1e-12)


def main():
    # 1) native RMS of AM classes at 30 dB
    with h5py.File(GOLD, "r") as f:
        Y = f["Y"][:]
        Z = f["Z"][:, 0]
        X = f["X"]
        print("native RMS (30dB, 200 frames):")
        for name in ["AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC", "AM-DSB-SC"]:
            q = np.where((Z == 30) & (Y[:, ORDER.index(name)] == 1))[0][:200]
            xr = (X[q][:, :, 0] + 1j * X[q][:, :, 1]).astype(np.complex128)
            rms = np.sqrt(np.mean(np.abs(xr) ** 2))
            print(f"  {name}: rms={rms:.4f}")

    ck = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    model = ADAMRV11Net(num_classes=24, **MODEL_KWARGS)
    model.load_state_dict(ck["model_state"])
    model.eval()

    def recall(m, target, nframes=2000, base=7_000_000):
        fr = np.stack([candidate(np.random.default_rng(base + i), m) for i in range(nframes)])
        xi = np.ascontiguousarray(np.stack([fr.real, fr.imag], axis=1)).astype(np.float32)
        with torch.inference_mode():
            out, _ = model(torch.from_numpy(xi))
        pred = out.numpy().argmax(axis=1)
        rec = float((pred == target).mean())
        cnt = Counter(pred.tolist())
        conf = ", ".join(f"{ORDER[k]}={v}" for k, v in sorted(cnt.items(), key=lambda kv: -kv[1])[:2])
        return rec, conf

    print("\nrobust recall (2000 frames):")
    for m in [0.10, 0.11, 0.12, 0.126]:
        rw, _ = recall(m, IDX["AM-DSB-WC"])
        print(f"  WC m={m:.3f}: rec={rw:.4f}")
    for m in [0.15, 0.175, 0.18, 0.20]:
        rs, cs = recall(m, IDX["AM-DSB-SC"])
        print(f"  SC m={m:.3f}: rec={rs:.4f}  (conf {cs})")


if __name__ == "__main__":
    main()
