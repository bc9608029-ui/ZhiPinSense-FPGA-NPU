"""Ground-truth recall table: all 17 digital classes, RRC vs wsinc pulse.

Uses the contract's exact constellations (imported) and generation flow, only
swapping the pulse.  This establishes the real baseline before I edit the
contract.
"""
from __future__ import annotations

import os
import sys

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

DIGITAL = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]


def sinc(x):
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(np.abs(x) < 1e-12, 1.0, np.sin(np.pi * x) / (np.pi * x))


def wsinc(fc=0.059, ntaps=65):
    n = np.arange(ntaps) - (ntaps - 1) / 2.0
    h = 2.0 * fc * sinc(2.0 * fc * n)
    h = h * np.hanning(ntaps)
    return h / np.sqrt(np.sum(h ** 2))


def main():
    ck = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    model = ADAMRV11Net(num_classes=24, **MODEL_KWARGS)
    model.load_state_dict(ck["model_state"])
    model.eval()

    def recall(x, idx):
        xi = np.ascontiguousarray(np.stack([x.real, x.imag], axis=1)).astype(np.float32)
        with torch.inference_mode():
            out, _ = model(torch.from_numpy(xi))
        return float((out.numpy().argmax(axis=1) == idx).mean())

    H_wsinc = wsinc()
    print(f"{'class':<9} {'RRC':>7} {'wsinc':>7}")
    table = {}
    for cidx in DIGITAL:
        name = c.LABEL_ORDER_24[cidx]
        row = {}
        # RRC (current contract _H)
        c._H = c.rrc_taps()
        fr_r = np.stack([c.generate_class(name, 5000 + i) for i in range(200)])
        row["rrc"] = round(recall(fr_r, cidx), 3)
        # wsinc
        c._H = H_wsinc
        fr_w = np.stack([c.generate_class(name, 5000 + i) for i in range(200)])
        row["wsinc"] = round(recall(fr_w, cidx), 3)
        table[name] = row
        print(f"{name:<9} {row['rrc']:>7} {row['wsinc']:>7}")

    c._H = c.rrc_taps()  # restore

    import json
    from pathlib import Path
    Path(r"F:/嵌赛/fix10clean2a_results/PROBE7_GROUND_TRUTH.json").write_text(
        json.dumps(table, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
