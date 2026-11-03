"""Refine 64APSK rings + search 128APSK rings (contract-exact generation)."""
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

    def recall(name, idx, nframes=300, base=300000):
        fr = np.stack([c.generate_class(name, base + i) for i in range(nframes)])
        xi = np.ascontiguousarray(np.stack([fr.real, fr.imag], axis=1)).astype(np.float32)
        with torch.inference_mode():
            out, _ = model(torch.from_numpy(xi))
        return float((out.numpy().argmax(axis=1) == idx).mean())

    # ---- 64APSK refine ----
    print("=== 64APSK refine (400 frames) ===")
    best = []
    for r2 in [1.8, 2.0, 2.2, 2.4]:
        for r3 in [3.0, 3.3, 3.6, 3.9]:
            for r4 in [5.0, 5.3, 5.6, 5.9]:
                c._apsk = make_apsk([(4, 1.0), (12, r2), (20, r3), (28, r4)])
                rec = recall("64APSK", 10, nframes=400)
                best.append((rec, r2, r3, r4))
    best.sort(reverse=True)
    print("top 64APSK:")
    for rec, r2, r3, r4 in best[:8]:
        print(f"  ({r2},{r3},{r4}) -> {rec:.3f}")

    # ---- 128APSK search (4+12+20+28+36+28) ----
    print("\n=== 128APSK search (160 frames) ===")
    best2 = []
    for r2 in [1.6, 2.0, 2.4]:
        for r3 in [2.4, 3.0, 3.6]:
            for r4 in [3.2, 4.0, 4.8]:
                for r5 in [4.2, 5.2, 6.4]:
                    for r6 in [5.4, 6.6, 8.0]:
                        c._apsk = make_apsk([(4, 1.0), (12, r2), (20, r3), (28, r4),
                                             (36, r5), (28, r6)])
                        rec = recall("128APSK", 11, nframes=160)
                        best2.append((rec, r2, r3, r4, r5, r6))
    best2.sort(reverse=True)
    print("top 128APSK:")
    for rec, r2, r3, r4, r5, r6 in best2[:10]:
        print(f"  ({r2},{r3},{r4},{r5},{r6}) -> {rec:.3f}")

    Path(r"F:/嵌赛/fix10clean2a_results/PROBE10_APSK_REFINE.json").write_text(
        json.dumps({"64": [[round(r, 3), *v] for r, *v in best[:20]],
                    "128": [[round(r, 3), *v] for r, *v in best2[:20]]}, indent=2),
        encoding="utf-8")
    print("\n-> PROBE10_APSK_REFINE.json")


if __name__ == "__main__":
    main()
