"""128APSK: test 5-ring (4+12+20+28+64) vs 6-ring-with-r5==r6, refine to >0.95."""
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

    def recall(rings, nframes=400, base=500000):
        c._apsk = make_apsk(rings)
        fr = np.stack([c.generate_class("128APSK", base + i) for i in range(nframes)])
        xi = np.ascontiguousarray(np.stack([fr.real, fr.imag], axis=1)).astype(np.float32)
        with torch.inference_mode():
            out, _ = model(torch.from_numpy(xi))
        return float((out.numpy().argmax(axis=1) == 11).mean())

    # 5-ring: 4+12+20+28+64
    print("=== 5-ring (4+12+20+28+64) search (400 frames) ===")
    best = []
    for r2 in [1.5, 1.7, 1.9, 2.1]:
        for r3 in [2.8, 3.2, 3.6, 4.0]:
            for r4 in [4.2, 4.8, 5.4]:
                for r5 in [6.0, 6.6, 7.2, 7.8]:
                    rings = [(4, 1.0), (12, r2), (20, r3), (28, r4), (64, r5)]
                    best.append((recall(rings), r2, r3, r4, r5))
    best.sort(reverse=True)
    print("top 5-ring:")
    for rec, r2, r3, r4, r5 in best[:8]:
        print(f"  ({r2},{r3},{r4},{r5}) -> {rec:.3f}")

    # 6-ring with r5==r6 (outer = 36+28 at same radius)
    print("\n=== 6-ring r5==r6 search (400 frames) ===")
    best2 = []
    for r2 in [1.5, 1.7, 1.9, 2.1]:
        for r3 in [2.8, 3.2, 3.6, 4.0]:
            for r4 in [4.2, 4.8, 5.4]:
                for r5 in [6.0, 6.6, 7.2, 7.8]:
                    rings = [(4, 1.0), (12, r2), (20, r3), (28, r4), (36, r5), (28, r5)]
                    best2.append((recall(rings), r2, r3, r4, r5))
    best2.sort(reverse=True)
    print("top 6-ring(r5=r6):")
    for rec, r2, r3, r4, r5 in best2[:8]:
        print(f"  ({r2},{r3},{r4},{r5}) -> {rec:.3f}")

    Path(r"F:/嵌赛/fix10clean2a_results/PROBE13_128_5RING.json").write_text(
        json.dumps({"5ring": [[round(r, 3), *v] for r, *v in best[:20]],
                    "6ring_eq": [[round(r, 3), *v] for r, *v in best2[:20]]}, indent=2),
        encoding="utf-8")
    print("\n-> PROBE13_128_5RING.json")


if __name__ == "__main__":
    main()
