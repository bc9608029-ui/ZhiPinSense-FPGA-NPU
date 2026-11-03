"""Test DVB-S2X 64/128APSK definitions (ring counts + radii) against the model.

DVB-S2X 128APSK = 6 rings, radii ratio R/R1 = (1, 1.715, 2.118, 2.681, 2.75,
3.819), counts 16+16+16+16+16+48.  DVB-S2X 64APSK has variants; test both
"8+16+20+20 @ (2.2,3.6,5.2)" and "4+12+20+28 @ (2.4,4.3,7.0)".
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


def make_apsk(rings, offset_per_ring=None):
    """rings = [(count, radius), ...].  offset_per_ring = optional list of
    per-ring phase offsets (radians), else a shared 0."""
    def _apsk(m):
        pts = []
        for i, (count, radius) in enumerate(rings):
            off = offset_per_ring[i] if offset_per_ring else 0.0
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

    def recall(name, idx, rings, nframes=500, base=700000, off=None):
        c._apsk = make_apsk(rings, off)
        fr = np.stack([c.generate_class(name, base + i) for i in range(nframes)])
        xi = np.ascontiguousarray(np.stack([fr.real, fr.imag], axis=1)).astype(np.float32)
        with torch.inference_mode():
            out, _ = model(torch.from_numpy(xi))
        return float((out.numpy().argmax(axis=1) == idx).mean())

    print("=== 128APSK structures (500 frames) ===")
    # (a) DVB-S2X 6-ring 16x5+48, radii 1.715..3.819
    rings_a = [(16, 1.0), (16, 1.715), (16, 2.118), (16, 2.681), (16, 2.75), (48, 3.819)]
    ra = recall("128APSK", 11, rings_a)
    print(f"(a) DVB-S2X 16x5+48 @(1.715,2.118,2.681,2.75,3.819) -> {ra:.3f}")

    # (b) same radii, counts 4+12+20+28+36+28
    rings_b = [(4, 1.0), (12, 1.715), (20, 2.118), (28, 2.681), (36, 2.75), (28, 3.819)]
    rb = recall("128APSK", 11, rings_b)
    print(f"(b) DVB-S2X radii, 4+12+20+28+36+28 -> {rb:.3f}")

    # (c) my current best
    rings_c = [(4, 1.0), (12, 1.8), (20, 3.3), (28, 4.8), (36, 6.6), (28, 6.6)]
    rc = recall("128APSK", 11, rings_c)
    print(f"(c) current (1.8,3.3,4.8,6.6,6.6) 4+12+20+28+36+28 -> {rc:.3f}")

    # (d) DVB-S2X radii x 4, with my structure and scaled counts
    rings_d = [(4, 1.0), (12, 1.715), (20, 2.118), (28, 2.681), (36, 2.75), (28, 3.819)]
    rd = recall("128APSK", 11, rings_d)
    print(f"(d) DVB-S2X radii x4, 4+12+20+28+36+28 -> {rd:.3f}")

    print("\n=== 64APSK structures (500 frames) ===")
    rings_e = [(8, 1.0), (16, 2.2), (20, 3.6), (20, 5.2)]      # DVB-S2X 8+16+20+20
    re = recall("64APSK", 10, rings_e)
    print(f"(e) DVB-S2X 8+16+20+20 @(2.2,3.6,5.2) -> {re:.3f}")

    rings_f = [(4, 1.0), (12, 2.4), (20, 4.3), (28, 7.0)]      # DVB-S2X 4+12+20+28
    rf = recall("64APSK", 10, rings_f)
    print(f"(f) DVB-S2X 4+12+20+28 @(2.4,4.3,7.0) -> {rf:.3f}")

    rings_g = [(4, 1.0), (12, 2.2), (20, 3.6), (28, 5.6)]      # my current
    rg = recall("64APSK", 10, rings_g)
    print(f"(g) current 4+12+20+28 @(2.2,3.6,5.6) -> {rg:.3f}")

    Path(r"F:/嵌赛/fix10clean2a_results/PROBE16_DVBS2X.json").write_text(
        json.dumps({"128": {"a_16x5p48": ra, "b_radii_4x": rb, "c_current": rc,
                            "d_radii4_4x": rd},
                    "64": {"e_8_16_20_20": re, "f_4_12_20_28_s2x": rf,
                           "g_current": rg}}, indent=2), encoding="utf-8")
    print("\n-> PROBE16_DVBS2X.json")


if __name__ == "__main__":
    main()
