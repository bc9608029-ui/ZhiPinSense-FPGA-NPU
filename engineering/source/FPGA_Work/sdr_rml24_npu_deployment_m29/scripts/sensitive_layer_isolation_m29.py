#!/usr/bin/env python
"""M29 Phase D.1 — read-only audit item #4: sensitive-layer isolation.

Locates the FIRST significant deviation for AM-SSB-SC by re-quantizing *only*
specific layers of the FP32 model with the EXACT vendor scales exported from
ZG.json / the quantize log, and measuring whether each alone reproduces the
AM-SSB-SC (class 18) collapse observed in the full vendor-INT8 model.

Vendor scales (from ZG.json + quantize log `Calculate Scale`):
  * final classifier head (op 179, MatmulNode) output "logits":
        scale = 1.2439321  (single shared value for all 24 dims), sint8
  * classifier FC1 (op 177, MatmulNode) output:
        scale = 0.12692387 (single shared value for 128 dims), sint8

This is a READ-ONLY audit: no model files are modified, no test data is read,
no config is changed. Only fp32 logits/activations are (re)computed in-memory.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

USER_SITE = r"C:\Users\shado\AppData\Roaming\Python\Python313\site-packages"
if os.path.isdir(USER_SITE) and USER_SITE not in sys.path:
    sys.path.insert(0, USER_SITE)

import numpy as np  # noqa: E402
import torch  # noqa: E402

ROOT = r"F:\FPGA_Work\sdr_rml24_npu_deployment_m29"
V11 = r"F:\FPGA_Work\sdr_amr_rml24_ood_v1_1"
CHECKPOINT = r"F:\FPGA_Work\24class_results\rml24_seed2027_best.pt"
HDF5_PATH = r"F:\datasets\RadioML2018\GOLD_XYZ_OSC.0001_1024.hdf5"
INDEX_PATH = os.path.join(V11, "data", "radioml2018", "rml24_split_indices.npz")

CHECKPOINT_SHA = "96cd25f87d6f6f8cacda94432136db9420f74300cecba71df3c9fbe49817be6d"
INDEX_SHA = "9a035841baef299ac918ae64294d59ba2298c5f20852862d3dd4069547330335"

SCALE_LOGITS = 1.2439321
SCALE_FC1 = 0.12692387

AM_SSB_SC = 18  # AM-SSB-SC
AM_SSB_WC = 17  # AM-SSB-WC
OOK = 0


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def quantize_int8(x: np.ndarray, scale: float) -> np.ndarray:
    """Symmetric int8 quantize/dequantize (zero_point=0, as in ZG.json)."""
    q = np.clip(np.round(x / scale), -127.0, 127.0)
    return q * scale


def main() -> int:
    print("== M29 Phase D.1: sensitive-layer isolation (read-only) ==")
    if sha256_file(CHECKPOINT) != CHECKPOINT_SHA:
        print("  FAIL: checkpoint sha"); return 1
    with open(INDEX_PATH, "rb") as f:
        if hashlib.sha256(f.read()).hexdigest() != INDEX_SHA:
            print("  FAIL: index sha"); return 1
    print("  [OK] checkpoint + split-index identity")

    sys.path.insert(0, V11)
    from contracts.rml24_contract import LABEL_ORDER_24
    from models.rml24_net import build_rml24_model
    ckpt = torch.load(CHECKPOINT, map_location="cpu", weights_only=True)
    cfg = {"denoiser_channels": 24, "denoiser_blocks": 3,
           "feature_channels": [32, 48, 64, 96], "classifier_hidden": 128, "dropout": 0.15}
    model = build_rml24_model(24, **cfg)
    model.load_state_dict(ckpt["model_state"], strict=True)
    model.eval()

    # introspect classifier module indices
    cls = model.classifier
    print("  classifier submodules:", [(i, type(m).__name__) for i, m in enumerate(cls)])

    d = np.load(os.path.join(ROOT, "work", "eval_full", "subset_index.npz"))
    sub_indices = d["sub_indices"]
    sub_labels = d["sub_labels"]
    N = len(sub_indices)

    import h5py
    def compute(mode: str) -> np.ndarray:
        """mode: 'fp32' | 'fc1_q' | 'logits_q'. Returns (N,24) logits."""
        logits = np.empty((N, 24), dtype=np.float32)
        hook = None
        if mode == "fc1_q":
            def h(module, inp, out):
                return torch.from_numpy(
                    quantize_int8(out.detach().numpy(), SCALE_FC1))
            hook = cls[0].register_forward_hook(h)
        with torch.inference_mode():
            with h5py.File(HDF5_PATH, "r") as f:
                X = f["X"]
                for i, src in enumerate(sub_indices.tolist()):
                    raw = np.asarray(X[src], dtype=np.float32)
                    planar = np.ascontiguousarray(raw.T)[None, :, :]
                    out, _ = model(torch.from_numpy(planar))
                    o = out.detach().numpy().reshape(-1)
                    if mode == "logits_q":
                        o = quantize_int8(o, SCALE_LOGITS)
                    logits[i] = o
        if hook is not None:
            hook.remove()
        return logits

    print("  computing fp32 logits ...")
    fp32 = compute("fp32")
    print("  computing FC1-output-only-quantized logits ...")
    fc1_q = compute("fc1_q")

    # vendor full-INT8 logits (already produced by icraft-run in Phase D)
    quant_logits = np.load(os.path.join(ROOT, "work", "eval_quant", "quant_logits.npy"))
    assert quant_logits.shape == (N, 24), quant_logits.shape

    # output-only quantization = apply vendor logits scale to fp32 logits
    logits_q = quantize_int8(fp32, SCALE_LOGITS)

    def metrics(logits: np.ndarray) -> dict:
        pred = logits.argmax(axis=1)
        acc = float((pred == sub_labels).mean())
        # per-class
        pca = [float((pred[sub_labels == c] == c).mean()) for c in range(24)]
        min_idx = int(np.argmin(pca))
        # AM-SSB-SC confusion
        m = sub_labels == AM_SSB_SC
        sc_pred = pred[m]
        sc_acc = float((sc_pred == AM_SSB_SC).mean())
        conf = {
            "AM-SSB-WC(17)": int((sc_pred == AM_SSB_WC).sum()),
            "OOK(0)": int((sc_pred == OOK).sum()),
            "AM-SSB-SC(18)": int((sc_pred == AM_SSB_SC).sum()),
            "other": int((~np.isin(sc_pred, [AM_SSB_WC, OOK, AM_SSB_SC])).sum()),
        }
        return {"accuracy": acc, "min_class": pca[min_idx],
                "min_class_idx": min_idx, "min_class_name": LABEL_ORDER_24[min_idx],
                "am_ssb_sc_acc": sc_acc, "am_ssb_sc_confusion": conf}

    res = {
        "phase": "M29-Phase-D.1-sensitive-layer-isolation",
        "scales": {"final_logits": SCALE_LOGITS, "classifier_fc1": SCALE_FC1},
        "fp32": metrics(fp32),
        "output_only_quantized": metrics(logits_q),
        "fc1_only_quantized": metrics(fc1_q),
        "vendor_full_int8": metrics(quant_logits),
        "top1_agreement": {
            "output_only_vs_vendor_full": float((logits_q.argmax(1) == quant_logits.argmax(1)).mean()),
            "fp32_vs_vendor_full": float((fp32.argmax(1) == quant_logits.argmax(1)).mean()),
            "fc1_only_vs_fp32": float((fc1_q.argmax(1) == fp32.argmax(1)).mean()),
        },
        "label_order": list(LABEL_ORDER_24),
        "split": "radioml2018_validation",
        "test_split_touched": False,
        "read_only": True,
    }
    out_dir = os.path.join(ROOT, "artifacts")
    os.makedirs(out_dir, exist_ok=True)
    p = os.path.join(out_dir, "m29_sensitive_layer_isolation.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    print(json.dumps(res, indent=2))
    print(f"  wrote {p}")
    print("== M29 sensitive-layer isolation PASS ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
