"""Confusion for 128APSK candidates + a finer 5-D search."""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
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


def make_apsk(rings):
    def _apsk(m):
        pts = []
        for count, radius in rings:
            off = np.random.default_rng(0).uniform(0, 2 * np.pi)
            for k in range(count):
                pts.append(radius * np.exp(1j * (2 * np.pi * k / count + off)))
        pts = np.array(pts)
        return pts / np.sqrt(np.mean(np.abs(pts) ** 2))
    return _apsk


def main():
    ck = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    model = ADAMRV11Net(num_classes=24, **MODEL_KWARGS)
    model.load_state_dict(ck["model_state"])
    model.eval()

    def predict(name, rings, nframes=400, base=400000):
        c._apsk = make_apsk(rings)
        fr = np.stack([c.generate_class(name, base + i) for i in range(nframes)])
        xi = np.ascontiguousarray(np.stack([fr.real, fr.imag], axis=1)).astype(np.float32)
        with torch.inference_mode():
            out, _ = model(torch.from_numpy(xi))
        return out.numpy().argmax(axis=1)

    # confusion for best-known candidate
    rings = [(4, 1.0), (12, 2.0), (20, 3.6), (28, 4.8), (36, 6.4), (28, 6.6)]
    pred = predict("128APSK", rings)
    rec = (pred == 11).mean()
    cnt = Counter(pred.tolist())
    top = sorted(cnt.items(), key=lambda kv: -kv[1])[:6]
    print(f"128APSK (2.0,3.6,4.8,6.4,6.6) recall={rec:.3f} conf=" +
          ", ".join(f"{ORDER[k]}={v}" for k, v in top))

    # finer search around (2.0,3.6,4.8,6.4,6.6)
    print("\n=== finer 128APSK search (300 frames) ===")
    best = []
    for r2 in [1.8, 2.0, 2.2]:
        for r3 in [3.3, 3.6, 3.9]:
            for r4 in [4.4, 4.8, 5.2]:
                for r5 in [5.8, 6.2, 6.6, 7.0]:
                    for r6 in [6.2, 6.6, 7.0, 7.4]:
                        rings = [(4, 1.0), (12, r2), (20, r3), (28, r4), (36, r5), (28, r6)]
                        pred = predict("128APSK", rings, nframes=300)
                        rec = (pred == 11).mean()
                        best.append((rec, r2, r3, r4, r5, r6))
    best.sort(reverse=True)
    print("top:")
    for rec, r2, r3, r4, r5, r6 in best[:10]:
        print(f"  ({r2},{r3},{r4},{r5},{r6}) -> {rec:.3f}")

    Path(r"F:/嵌赛/fix10clean2a_results/PROBE12_128.json").write_text(
        json.dumps([[round(r, 3), *v] for r, *v in best[:30]], indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
