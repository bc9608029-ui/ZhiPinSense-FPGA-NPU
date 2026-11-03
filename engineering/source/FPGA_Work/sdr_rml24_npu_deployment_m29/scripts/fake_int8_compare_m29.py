#!/usr/bin/env python
"""M29 Phase C2 — fake-INT8 (symmetric per-tensor weights/127) vs fp32 on validation.

Mirrors `_apply_fake_int8` from `_frozen/evaluation/evaluate_rml24.py` exactly:
every parameter (weights, biases, BatchNorm gamma/beta) is quantized per-tensor to
7-bit signed integers (scale = max|w|/127), activations stay fp32.  This is the
"fake symmetric int8 weights, fp32 activations" numeric mode, NOT vendor INT8
(which additionally quantizes activations per-channel with KLD saturation).

Runs fp32 and fake-int8 top-1 evaluation on the SAME bounded stratified validation
subset (NOT test) and reports the accuracy delta, per-class recall, rated_0_20 and
confusion matrices.

Writes work/fake_int8/fake_int8_report.json + artifacts/m29_fake_int8_report.json.
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

SEED = 2027
BATCH_SIZE = 512
DEFAULT_SAMPLES = 131072  # bounded stratified subset of the 511,056-sample validation split


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def _apply_fake_int8(model: torch.nn.Module) -> None:
    """Byte-for-byte mirror of _frozen/evaluation/evaluate_rml24.py::_apply_fake_int8."""
    with torch.no_grad():
        for parameter in model.parameters():
            maximum = float(parameter.abs().max())
            if maximum > 0.0:
                scale = maximum / 127.0
                parameter.copy_(torch.clamp(torch.round(parameter / scale), -127, 127) * scale)


def _stratified_indices(labels: np.ndarray, snrs: np.ndarray, limit: int, seed: int) -> list[int]:
    """Deterministic representative subset across (class, SNR) strata (mirrors the
    frozen `_stratified_indices` so the bounded subset keeps the full split's
    class/SNR distribution)."""
    n = int(len(labels))
    if limit >= n:
        return list(range(n))
    strata: dict[tuple[int, float], list[int]] = {}
    for position in range(n):
        strata.setdefault((int(labels[position]), float(snrs[position])), []).append(position)
    allocations = {key: int(len(positions) * limit / n) for key, positions in strata.items()}
    remaining = limit - sum(allocations.values())
    for key in sorted(strata, key=lambda k: (-len(strata[k]), k)):
        if remaining <= 0:
            break
        if allocations[key] < len(strata[key]):
            allocations[key] += 1
            remaining -= 1
    rng = np.random.default_rng(seed)
    chosen: list[int] = []
    for key, positions in strata.items():
        allocation = allocations[key]
        if allocation <= 0:
            continue
        order = np.asarray(positions, dtype=np.int64)
        rng.shuffle(order)
        chosen.extend(int(v) for v in order[:allocation].tolist())
    chosen.sort()
    return chosen


def _summary(targets: list[int], predictions: list[int], snrs: list[float],
             num_classes: int) -> dict:
    """Top-1 metrics mirroring training.ad_amr_v1_1_trainer._summary (numpy-only)."""
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

    per_snr: dict[str, float] = {}
    for value in sorted(set(snrs.tolist())):
        per_snr[f"{value:.0f}"] = slice_accuracy(lambda s, value=value: s == value)

    # macro-F1 = mean per-class F1 (mirror sklearn average="macro", zero_division=0)
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


def _evaluate(model: torch.nn.Module, indices: np.ndarray, labels: np.ndarray,
              snrs: np.ndarray, hdf5_x) -> dict:
    targets: list[int] = []
    predictions: list[int] = []
    snr_list: list[float] = []
    with torch.inference_mode():
        for start in range(0, len(indices), BATCH_SIZE):
            stop = min(start + BATCH_SIZE, len(indices))
            rows = indices[start:stop]
            raw = np.asarray(hdf5_x[rows.tolist()], dtype=np.float32)  # [B, 1024, 2]
            planar = np.ascontiguousarray(raw.transpose(0, 2, 1))       # [B, 2, 1024]
            x = torch.from_numpy(planar)
            out, _ = model(x)
            if not bool(torch.isfinite(out).all()):
                raise RuntimeError("non-finite logits in evaluation")
            targets.extend(int(v) for v in labels[start:stop].tolist())
            predictions.extend(int(v) for v in out.argmax(1).tolist())
            snr_list.extend(float(v) for v in snrs[start:stop].tolist())
    return _summary(targets, predictions, snr_list, 24)


def main() -> int:
    print("== M29 Phase C2: fake-INT8 vs fp32 (validation-only) ==")

    if len(sys.argv) > 1:
        samples = int(sys.argv[1])
    else:
        samples = DEFAULT_SAMPLES

    print("[1/5] identity gates")
    ckpt_sha = sha256_file(CHECKPOINT)
    if ckpt_sha != CHECKPOINT_SHA:
        print(f"  FAIL: checkpoint sha {ckpt_sha} != {CHECKPOINT_SHA}")
        return 1
    with open(INDEX_PATH, "rb") as f:
        index_sha = hashlib.sha256(f.read()).hexdigest()
    if index_sha != INDEX_SHA:
        print(f"  FAIL: index sha {index_sha} != {INDEX_SHA}")
        return 1
    print(f"  [OK] checkpoint_sha256={ckpt_sha[:16]}... index_sha256={index_sha[:16]}...")

    print("[2/5] load checkpoint (weights_only=True) + strict build")
    sys.path.insert(0, V11)
    from contracts.rml24_contract import LABEL_ORDER_24
    from models.rml24_net import build_rml24_model
    ckpt = torch.load(CHECKPOINT, map_location="cpu", weights_only=True)
    assert list(ckpt["class_names"]) == list(LABEL_ORDER_24), "class order drift"
    model_cfg = {
        "denoiser_channels": 24, "denoiser_blocks": 3,
        "feature_channels": [32, 48, 64, 96], "classifier_hidden": 128, "dropout": 0.15,
    }
    model = build_rml24_model(24, **model_cfg)
    model.load_state_dict(ckpt["model_state"], strict=True)
    model.eval()
    print(f"  [OK] strict load; params={sum(p.numel() for p in model.parameters())}")

    print("[3/5] load validation split (NOT test)")
    with np.load(INDEX_PATH, allow_pickle=False) as idx:
        val_indices = idx["validation_indices"].astype(np.int64, copy=True)
        val_labels = idx["validation_labels"].astype(np.int64, copy=True)
        val_snrs = idx["validation_snrs"].astype(np.float32, copy=True)
    chosen = _stratified_indices(val_labels, val_snrs, samples, SEED)
    sel_indices = val_indices[chosen]
    sel_labels = val_labels[chosen]
    sel_snrs = val_snrs[chosen]
    # h5py fancy indexing requires increasing row indices; order is irrelevant to
    # the count-based metrics, so sort the whole triple by source row.
    order = np.argsort(sel_indices)
    sel_indices = sel_indices[order]
    sel_labels = sel_labels[order]
    sel_snrs = sel_snrs[order]
    print(f"  validation full={len(val_indices)}, bounded stratified subset={len(chosen)}")

    import h5py
    with h5py.File(HDF5_PATH, "r") as f:
        hdf5_x = f["X"]

        print("[4/5] fp32 evaluation")
        fp32 = _evaluate(model, sel_indices, sel_labels, sel_snrs, hdf5_x)
        print(f"  fp32 accuracy={fp32['accuracy']:.6f} "
              f"rated_0_20={fp32['rated_0_20_accuracy']:.6f} "
              f"min_class={fp32['min_per_class_accuracy']:.6f}")

        print("[5/5] fake-INT8 evaluation")
        _apply_fake_int8(model)
        int8 = _evaluate(model, sel_indices, sel_labels, sel_snrs, hdf5_x)
        print(f"  int8 accuracy={int8['accuracy']:.6f} "
              f"rated_0_20={int8['rated_0_20_accuracy']:.6f} "
              f"min_class={int8['min_per_class_accuracy']:.6f}")

    accuracy_drop = fp32["accuracy"] - int8["accuracy"]
    rated_drop = fp32["rated_0_20_accuracy"] - int8["rated_0_20_accuracy"]
    per_class_delta = [fp32["per_class_accuracy"][c] - int8["per_class_accuracy"][c]
                       for c in range(24)]
    print(f"\n  accuracy_drop={accuracy_drop:+.6f} rated_0_20_drop={rated_drop:+.6f} "
          f"max_per_class_drop={max(per_class_delta):+.6f}")

    report = {
        "phase": "M29-Phase-C2-fake-int8-vs-fp32",
        "checkpoint": CHECKPOINT,
        "checkpoint_sha256": CHECKPOINT_SHA,
        "checkpoint_epoch": int(ckpt.get("epoch")),
        "model_name": "RML2018_24_BENCHMARK",
        "class_count": 24,
        "label_order": list(LABEL_ORDER_24),
        "split": "radioml2018_validation",
        "test_split_touched": False,
        "numeric_mode_fp32": "fp32",
        "numeric_mode_fake_int8": "fake_symmetric_int8_weights_fp32_activations",
        "fake_int8_scheme": "per-tensor symmetric scale=max|w|/127, clamp [-127,127], activations fp32",
        "samples": int(len(chosen)),
        "validation_full_size": int(len(val_indices)),
        "stratified": True,
        "seed": SEED,
        "batch_size": BATCH_SIZE,
        "fp32": {k: v for k, v in fp32.items() if k != "confusion_matrix"},
        "fake_int8": {k: v for k, v in int8.items() if k != "confusion_matrix"},
        "fp32_confusion": fp32["confusion_matrix"],
        "fake_int8_confusion": int8["confusion_matrix"],
        "accuracy_drop": accuracy_drop,
        "rated_0_20_drop": rated_drop,
        "selection_score_drop": fp32["selection_score"] - int8["selection_score"],
        "per_class_accuracy_drop": per_class_delta,
        "max_per_class_drop": max(per_class_delta),
    }
    out_dir = os.path.join(ROOT, "work", "fake_int8")
    os.makedirs(out_dir, exist_ok=True)
    for path in (os.path.join(out_dir, "fake_int8_report.json"),
                 os.path.join(ROOT, "artifacts", "m29_fake_int8_report.json")):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"  wrote {path}")

    print("== M29 Phase C2 PASS ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
