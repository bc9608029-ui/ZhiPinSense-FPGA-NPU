#!/usr/bin/env python
"""M29 Phase D — regenerate the bounded stratified subset + ONNX agreement.

The full-validation fp32/fake-INT8 pass already completed (results printed to its
log; see full_validation_eval_m29.py).  That run crashed in the subset-sampling
step (now fixed), so this script reproduces ONLY steps [5/6]:

  * draw the 64/class stratified subset (seed 2028) deterministically
  * fp32 predictions on the subset (reference for the icraft-run agreement)
  * fake-INT8 predictions on the subset (for the sub_int8 column)
  * ONNX (batch=1) predictions on the subset -> Top-1 agreement vs fp32
  * save work/eval_full/subset_index.npz (consumed by quantized_agreement_m29.py)

Fail-closed: checkpoint + split-index SHA must match frozen values.
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
ONNX_PATH = os.path.join(ROOT, "work", "onnx", "rml24_24class_opset17.onnx")

CHECKPOINT_SHA = "96cd25f87d6f6f8cacda94432136db9420f74300cecba71df3c9fbe49817be6d"
INDEX_SHA = "9a035841baef299ac918ae64294d59ba2298c5f20852862d3dd4069547330335"

SUBSET_PER_CLASS = 64
SUBSET_SEED = 2028


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def _apply_fake_int8(model: torch.nn.Module) -> None:
    with torch.no_grad():
        for parameter in model.parameters():
            maximum = float(parameter.abs().max())
            if maximum > 0.0:
                scale = maximum / 127.0
                parameter.copy_(torch.clamp(torch.round(parameter / scale), -127, 127) * scale)


def _stratified_subset(labels, snrs, per_class, seed) -> np.ndarray:
    """Deterministic per-class draw (stratified by SNR), returns positions into labels."""
    rng = np.random.default_rng(seed)
    positions = []
    for label in range(24):
        idx = np.flatnonzero(labels == label)          # positions into full array
        class_snrs = snrs[idx]                          # SNR of this class's samples
        unique_snrs = sorted(set(class_snrs.tolist()))
        base = per_class // len(unique_snrs)            # per-SNR floor allocation
        rem = per_class - base * len(unique_snrs)       # spread remainder over first SNRs
        picks: list[int] = []
        for snr in unique_snrs:
            sub = np.flatnonzero(class_snrs == snr)     # positions within this class
            n = min(base + (1 if rem > 0 else 0), len(sub))
            if rem > 0:
                rem -= 1
            order = sub.copy(); rng.shuffle(order)
            picks.extend(int(v) for v in order[:n])
        picks = list(dict.fromkeys(picks))              # dedup, keep order
        if len(picks) < per_class:                       # pad if a stratum was thin
            remaining = [int(i) for i in range(len(idx)) if int(i) not in picks]
            order = remaining; rng.shuffle(order)
            picks.extend(int(v) for v in order[: per_class - len(picks)])
        positions.extend(int(idx[p]) for p in picks[:per_class])
    positions.sort()
    return np.asarray(positions, dtype=np.int64)


def main() -> int:
    print("== M29 Phase D: subset + ONNX agreement (fp32/fake-INT8 full pass already done) ==")

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
    assert list(ckpt["class_names"]) == list(LABEL_ORDER_24), "class order drift"
    cfg = {"denoiser_channels": 24, "denoiser_blocks": 3, "feature_channels": [32, 48, 64, 96],
           "classifier_hidden": 128, "dropout": 0.15}
    model = build_rml24_model(24, **cfg)
    model.load_state_dict(ckpt["model_state"], strict=True)
    model.eval()

    import h5py
    with np.load(INDEX_PATH, allow_pickle=False) as idx:
        val_indices = idx["validation_indices"].astype(np.int64, copy=True)
        val_labels = idx["validation_labels"].astype(np.int64, copy=True)
        val_snrs = idx["validation_snrs"].astype(np.float32, copy=True)
    order = np.argsort(val_indices)
    val_indices = val_indices[order]
    sorted_labels = val_labels[order]
    sorted_snrs = val_snrs[order]

    sub_pos = _stratified_subset(sorted_labels, sorted_snrs, SUBSET_PER_CLASS, SUBSET_SEED)
    sub_indices = val_indices[sub_pos]
    sub_labels = sorted_labels[sub_pos]
    sub_snrs = sorted_snrs[sub_pos]
    print(f"  subset = {len(sub_pos)} samples ({SUBSET_PER_CLASS}/class)")

    def predict_subset(mod):
        preds = []
        with torch.inference_mode():
            with h5py.File(HDF5_PATH, "r") as f:
                X = f["X"]
                for src in sub_indices.tolist():
                    raw = np.asarray(X[src], dtype=np.float32)     # [1024, 2]
                    planar = np.ascontiguousarray(raw.T)[None, :, :]  # [1, 2, 1024]
                    out, _ = mod(torch.from_numpy(planar))
                    if not bool(torch.isfinite(out).all()):
                        raise RuntimeError("non-finite logits")
                    preds.append(int(out.argmax()))
        return np.asarray(preds, dtype=np.int64)

    sub_fp32 = predict_subset(model)
    _apply_fake_int8(model)
    sub_int8 = predict_subset(model)
    fp32_acc = float((sub_fp32 == sub_labels).mean())
    int8_acc = float((sub_int8 == sub_labels).mean())
    print(f"  subset fp32 acc={fp32_acc:.6f}  fake-INT8 acc={int8_acc:.6f}  "
          f"agree={float((sub_fp32 == sub_int8).mean()):.6f}")

    import onnxruntime as ort
    so = ort.SessionOptions(); so.log_severity_level = 3
    sess = ort.InferenceSession(ONNX_PATH, sess_options=so, providers=["CPUExecutionProvider"])
    onnx_pred = []
    with h5py.File(HDF5_PATH, "r") as f:
        X = f["X"]
        for src in sub_indices.tolist():
            raw = np.asarray(X[src], dtype=np.float32)
            planar = np.ascontiguousarray(raw.T)[None, :, :]
            out = sess.run(["logits"], {"iq": planar})[0]
            onnx_pred.append(int(out[0].argmax()))
    onnx_pred = np.asarray(onnx_pred, dtype=np.int64)
    onnx_acc = float((onnx_pred == sub_labels).mean())
    onnx_agree = float((onnx_pred == sub_fp32).mean())
    print(f"  ONNX acc={onnx_acc:.6f}  Top-1 agreement vs fp32 = {onnx_agree:.6f}")

    out_dir = os.path.join(ROOT, "work", "eval_full")
    os.makedirs(out_dir, exist_ok=True)
    np.savez(os.path.join(out_dir, "subset_index.npz"),
             sub_indices=sub_indices, sub_labels=sub_labels, sub_snrs=sub_snrs,
             sub_fp32=sub_fp32, sub_int8=sub_int8)
    report = {
        "phase": "M29-Phase-D-subset-onnx-agreement",
        "subset": {
            "per_class": SUBSET_PER_CLASS,
            "size": int(len(sub_pos)),
            "seed": SUBSET_SEED,
            "fp32_accuracy": fp32_acc,
            "fake_int8_accuracy": int8_acc,
            "fake_int8_top1_agreement_vs_fp32": float((sub_fp32 == sub_int8).mean()),
            "onnx_accuracy": onnx_acc,
            "onnx_top1_agreement_vs_fp32": onnx_agree,
            "onnx_top1_agreement_vs_int8": float((onnx_pred == sub_int8).mean()),
        },
        "label_order": list(LABEL_ORDER_24),
        "split": "radioml2018_validation",
        "test_split_touched": False,
    }
    path = os.path.join(out_dir, "subset_onnx_agreement_report.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"  wrote {path}")
    print("== M29 subset + ONNX agreement PASS ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
