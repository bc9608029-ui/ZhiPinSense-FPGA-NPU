#!/usr/bin/env python
"""M29 Phase D — full-validation evaluation: fp32 vs fake-INT8 (plus ONNX agreement).

This is the requirement-#6.4 host-side accuracy measurement on the FULL
radioml2018 validation split (511,056 samples, NOT test):

  * fp32 (PyTorch checkpoint)  -> reference accuracy / macro-F1 / rated_0_20 / snr0 / min_class
  * fake-INT8 (per-tensor symmetric weights/127, fp32 activations) -> weight-quantization proxy
  * ONNX (rml24_24class_opset17.onnx, batch=1) -> export-faithfulness check (Top-1 agreement vs fp32)

The ACTUAL vendor INT8 model (weights + activations + output, per-channel KLD) is
evaluated separately on a bounded stratified subset via icraft-run (see
icraft_run_agreement_m29.sh); this script saves the fp32 predictions + labels of
that same subset so the agreement can be computed against them.

Fail-closed gates: checkpoint SHA + split-index SHA must match the frozen values.
Writes work/eval_full/{fp32_preds.npy, int8_preds.npy, subset_index.npz,
full_validation_report.json} + artifacts/m29_full_validation_report.json.
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

SEED = 2027
BATCH_SIZE = 512
SUBSET_PER_CLASS = 64          # bounded stratified subset for ONNX + icraft-run agreement
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


def _summary(targets, predictions, snrs, num_classes: int) -> dict:
    targets = np.asarray(targets, dtype=np.int64)
    predictions = np.asarray(predictions, dtype=np.int64)
    snrs = np.asarray(snrs, dtype=np.float32)
    cm = np.zeros((num_classes, num_classes), dtype=np.int64)
    np.add.at(cm, (targets, predictions), 1)
    row_sum = cm.sum(axis=1)
    per_class = np.divide(np.diag(cm), row_sum, out=np.zeros(num_classes, dtype=float),
                          where=row_sum > 0)
    correct = (predictions == targets)
    accuracy = float(correct.mean())

    def slice_accuracy(predicate) -> float:
        sel = correct[predicate(snrs)]
        return float(sel.mean()) if len(sel) else 0.0

    per_snr = {f"{v:.0f}": slice_accuracy(lambda s, value=v: s == value)
               for v in sorted(set(snrs.tolist()))}
    f1s = []
    for c in range(num_classes):
        tp = cm[c, c]
        fp = cm[:, c].sum() - tp
        fn = row_sum[c] - tp
        f1s.append(2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) > 0 else 0.0)
    macro_f1 = float(np.mean(f1s))
    result = {
        "accuracy": accuracy,
        "macro_f1": macro_f1,
        "per_class_accuracy": [float(v) for v in per_class],
        "min_per_class_accuracy": float(per_class.min()),
        "rated_0_20_accuracy": slice_accuracy(lambda s: (s >= 0.0) & (s <= 20.0)),
        "high_10_20_accuracy": slice_accuracy(lambda s: (s >= 10.0) & (s <= 20.0)),
        "snr_0_accuracy": slice_accuracy(lambda s: s == 0.0),
        "per_snr_accuracy": per_snr,
        "confusion_matrix": cm.astype(int).tolist(),
    }
    result["selection_score"] = (
        0.45 * result["macro_f1"] + 0.30 * result["rated_0_20_accuracy"]
        + 0.15 * result["snr_0_accuracy"] + 0.10 * result["min_per_class_accuracy"]
    )
    return result


def _batched_predict(model, indices, hdf5_x) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    preds: list[int] = []
    targets: list[int] = []
    snrs: list[float] = []
    labels = np.asarray(sorted_labels)
    snr_arr = np.asarray(sorted_snrs)
    with torch.inference_mode():
        for start in range(0, len(indices), BATCH_SIZE):
            stop = min(start + BATCH_SIZE, len(indices))
            rows = indices[start:stop]
            raw = np.asarray(hdf5_x[rows.tolist()], dtype=np.float32)  # [B, 1024, 2]
            planar = np.ascontiguousarray(raw.transpose(0, 2, 1))       # [B, 2, 1024]
            x = torch.from_numpy(planar)
            out, _ = model(x)
            if not bool(torch.isfinite(out).all()):
                raise RuntimeError("non-finite logits")
            preds.extend(int(v) for v in out.argmax(1).tolist())
            targets.extend(int(v) for v in labels[start:stop].tolist())
            snrs.extend(float(v) for v in snr_arr[start:stop].tolist())
    return np.asarray(preds, dtype=np.int64), np.asarray(targets, dtype=np.int64), np.asarray(snrs, dtype=np.float32)


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
    print("== M29 Phase D: full-validation fp32 vs fake-INT8 (+ ONNX agreement) ==")

    print("[1/6] identity gates")
    if sha256_file(CHECKPOINT) != CHECKPOINT_SHA:
        print("  FAIL: checkpoint sha"); return 1
    with open(INDEX_PATH, "rb") as f:
        if hashlib.sha256(f.read()).hexdigest() != INDEX_SHA:
            print("  FAIL: index sha"); return 1
    print("  [OK] checkpoint + split-index identity")

    print("[2/6] build fp32 model (strict)")
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

    print("[3/6] load full validation split (NOT test)")
    import h5py
    with np.load(INDEX_PATH, allow_pickle=False) as idx:
        val_indices = idx["validation_indices"].astype(np.int64, copy=True)
        val_labels = idx["validation_labels"].astype(np.int64, copy=True)
        val_snrs = idx["validation_snrs"].astype(np.float32, copy=True)
    # sort by source row for h5py fancy indexing
    order = np.argsort(val_indices)
    val_indices = val_indices[order]
    global sorted_labels, sorted_snrs
    sorted_labels = val_labels[order]
    sorted_snrs = val_snrs[order]
    print(f"  validation full size = {len(val_indices)}")

    print("[4/6] full-validation fp32 + fake-INT8 evaluation")
    with h5py.File(HDF5_PATH, "r") as f:
        hdf5_x = f["X"]
        fp32_pred, fp32_target, fp32_snr = _batched_predict(model, val_indices, hdf5_x)
        _apply_fake_int8(model)
        int8_pred, int8_target, int8_snr = _batched_predict(model, val_indices, hdf5_x)
    assert np.array_equal(fp32_target, int8_target) and np.array_equal(fp32_snr, int8_snr)
    fp32 = _summary(fp32_target, fp32_pred, fp32_snr, 24)
    int8 = _summary(int8_target, int8_pred, int8_snr, 24)
    fp32_agree = float((fp32_pred == int8_pred).mean())
    print(f"  fp32  acc={fp32['accuracy']:.6f} macro_f1={fp32['macro_f1']:.6f} "
          f"rated_0_20={fp32['rated_0_20_accuracy']:.6f} snr0={fp32['snr_0_accuracy']:.6f} "
          f"min_class={fp32['min_per_class_accuracy']:.6f}")
    print(f"  int8  acc={int8['accuracy']:.6f} macro_f1={int8['macro_f1']:.6f} "
          f"rated_0_20={int8['rated_0_20_accuracy']:.6f} snr0={int8['snr_0_accuracy']:.6f} "
          f"min_class={int8['min_per_class_accuracy']:.6f}")
    print(f"  fake-INT8 Top-1 agreement vs fp32 = {fp32_agree:.6f}")

    print("[5/6] bounded stratified subset + ONNX agreement")
    sub_pos = _stratified_subset(sorted_labels, sorted_snrs, SUBSET_PER_CLASS, SUBSET_SEED)
    sub_indices = val_indices[sub_pos]
    sub_labels = sorted_labels[sub_pos]
    sub_snrs = sorted_snrs[sub_pos]
    sub_fp32 = fp32_pred[sub_pos]
    sub_int8 = int8_pred[sub_pos]
    print(f"  subset = {len(sub_pos)} samples ({SUBSET_PER_CLASS}/class)")

    import onnxruntime as ort
    so = ort.SessionOptions(); so.log_severity_level = 3
    sess = ort.InferenceSession(ONNX_PATH, sess_options=so, providers=["CPUExecutionProvider"])
    onnx_pred = []
    with h5py.File(HDF5_PATH, "r") as f:
        hdf5_x = f["X"]
        for i, src in enumerate(sub_indices.tolist()):
            raw = np.asarray(hdf5_x[src], dtype=np.float32)      # [1024, 2]
            planar = np.ascontiguousarray(raw.T)[None, :, :]     # [1, 2, 1024]
            out = sess.run(["logits"], {"iq": planar})[0]        # [1, 24]
            onnx_pred.append(int(out[0].argmax()))
    onnx_pred = np.asarray(onnx_pred, dtype=np.int64)
    onnx_acc = float((onnx_pred == sub_labels).mean())
    onnx_agree = float((onnx_pred == sub_fp32).mean())
    print(f"  ONNX acc={onnx_acc:.6f}  Top-1 agreement vs fp32 = {onnx_agree:.6f}")

    print("[6/6] write report + saved predictions")
    out_dir = os.path.join(ROOT, "work", "eval_full")
    os.makedirs(out_dir, exist_ok=True)
    np.save(os.path.join(out_dir, "fp32_preds.npy"), fp32_pred)
    np.save(os.path.join(out_dir, "int8_preds.npy"), int8_pred)
    np.savez(os.path.join(out_dir, "subset_index.npz"),
             sub_indices=sub_indices, sub_labels=sub_labels, sub_snrs=sub_snrs,
             sub_fp32=sub_fp32, sub_int8=sub_int8)
    report = {
        "phase": "M29-Phase-D-full-validation-fp32-vs-fake-int8-vs-onnx",
        "checkpoint_sha256": CHECKPOINT_SHA,
        "model_name": "RML2018_24_BENCHMARK",
        "label_order": list(LABEL_ORDER_24),
        "split": "radioml2018_validation",
        "test_split_touched": False,
        "validation_full_size": int(len(val_indices)),
        "batch_size": BATCH_SIZE,
        "fake_int8_scheme": "per-tensor symmetric weights/127, fp32 activations (weight-quantization proxy, NOT vendor per-channel KLD)",
        "fp32": {k: v for k, v in fp32.items() if k != "confusion_matrix"},
        "fake_int8": {k: v for k, v in int8.items() if k != "confusion_matrix"},
        "accuracy_drop": fp32["accuracy"] - int8["accuracy"],
        "macro_f1_drop": fp32["macro_f1"] - int8["macro_f1"],
        "rated_0_20_drop": fp32["rated_0_20_accuracy"] - int8["rated_0_20_accuracy"],
        "snr0_drop": fp32["snr_0_accuracy"] - int8["snr_0_accuracy"],
        "min_class_drop": fp32["min_per_class_accuracy"] - int8["min_per_class_accuracy"],
        "fake_int8_top1_agreement_vs_fp32": fp32_agree,
        "subset": {
            "per_class": SUBSET_PER_CLASS,
            "size": int(len(sub_pos)),
            "seed": SUBSET_SEED,
            "onnx_accuracy": onnx_acc,
            "onnx_top1_agreement_vs_fp32": onnx_agree,
            "onnx_top1_agreement_vs_int8": float((onnx_pred == sub_int8).mean()),
        },
    }
    for path in (os.path.join(out_dir, "full_validation_report.json"),
                 os.path.join(ROOT, "artifacts", "m29_full_validation_report.json")):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"  wrote {path}")
    print("== M29 full-validation eval PASS ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
