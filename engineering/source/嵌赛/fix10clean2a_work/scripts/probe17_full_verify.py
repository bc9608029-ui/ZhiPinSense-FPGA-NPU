"""Full 24-class verification of the clean generator against the frozen model.

Reports per-class raw24 recall + top confusion, plus raw24 and deployed23
(AM-SSB-WC/SC merged) overall & macro accuracy.  This is a Phase-3 pre-check
of the generator contract before writing the real dev/formal files.
"""
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
NF = 500
BASE = 900000

# 24 -> 23 deployed mapping (logaddexp merge of source 17/18 -> deployed 17).
SRC_TO_DEP = list(range(24))
SRC_TO_DEP[18] = 17   # AM-SSB-SC merges into AM-SSB-WC (deployed 17)
SRC_TO_DEP[19] = 18   # AM-DSB-WC -> 18
SRC_TO_DEP[20] = 19   # AM-DSB-SC -> 19
SRC_TO_DEP[21] = 20   # FM -> 20
SRC_TO_DEP[22] = 21   # GMSK -> 21
SRC_TO_DEP[23] = 22   # OQPSK -> 22


def main():
    ck = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    model = ADAMRV11Net(num_classes=24, **MODEL_KWARGS)
    model.load_state_dict(ck["model_state"])
    model.eval()

    per_class = {}
    all_pred = np.zeros(24 * NF, dtype=np.int64)
    all_true = np.zeros(24 * NF, dtype=np.int64)

    for ci, name in enumerate(ORDER):
        fr = np.stack([c.generate_class(name, BASE + ci * 100000 + i) for i in range(NF)])
        xi = np.ascontiguousarray(np.stack([fr.real, fr.imag], axis=1)).astype(np.float32)
        with torch.inference_mode():
            out, _ = model(torch.from_numpy(xi))
        pred = out.numpy().argmax(axis=1)
        rec = float((pred == ci).mean())
        cnt = Counter(pred.tolist())
        top = sorted(cnt.items(), key=lambda kv: -kv[1])[:3]
        conf = ", ".join(f"{ORDER[k]}={v}" for k, v in top if k != ci)
        per_class[name] = rec
        all_pred[ci * NF:(ci + 1) * NF] = pred
        all_true[ci * NF:(ci + 1) * NF] = ci
        print(f"{name:<10} raw24 recall={rec:.3f}   (conf: {conf or '-'})")

    # raw24 metrics
    raw_overall = float((all_pred == all_true).mean())
    raw_macro = float(np.mean([per_class[n] for n in ORDER]))
    print(f"\nraw24  overall={raw_overall:.4f}  macro={raw_macro:.4f}")

    # deployed23 metrics
    dep_true = np.array([SRC_TO_DEP[t] for t in all_true])
    dep_pred = np.array([SRC_TO_DEP[p] for p in all_pred])
    dep_overall = float((dep_pred == dep_true).mean())
    dep_rec = {}
    for t in sorted(set(dep_true)):
        m = dep_true == t
        dep_rec[t] = float((dep_pred[m] == t).mean())
    dep_macro = float(np.mean(list(dep_rec.values())))
    worst = sorted(dep_rec.items(), key=lambda kv: kv[1])[:5]
    print(f"deployed23 overall={dep_overall:.4f}  macro={dep_macro:.4f}")
    print("deployed23 worst recalls:")
    for t, r in worst:
        lbl = ORDER[t] if t < 24 else f"AM-SSB(merged {t})"
        print(f"  {lbl:<18} {r:.3f}")

    Path(r"F:/嵌赛/fix10clean2a_results/PROBE17_FULL_VERIFY.json").write_text(
        json.dumps({"raw24_overall": raw_overall, "raw24_macro": raw_macro,
                    "deployed23_overall": dep_overall, "deployed23_macro": dep_macro,
                    "per_class_raw24": per_class,
                    "per_deployed_recall": {str(k): v for k, v in dep_rec.items()}},
                   indent=2), encoding="utf-8")
    print("\n-> PROBE17_FULL_VERIFY.json")


if __name__ == "__main__":
    main()
