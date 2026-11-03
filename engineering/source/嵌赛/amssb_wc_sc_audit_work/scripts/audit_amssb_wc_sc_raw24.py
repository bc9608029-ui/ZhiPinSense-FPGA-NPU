#!/usr/bin/env python3
"""Phase A — AM-SSB-WC vs AM-SSB-SC distinguishability audit: FP32 clean test.

Answers question 1 of the task book ("can the frozen FP32 PyTorch model tell
WC from SC?") on the clean-condition data alone, before any quantization, board
NPU or RF link is involved.

Runs the FROZEN PyTorch model (checkpoint SHA 96cd25f8..., never retrained) on a
FIXED selection of 100 AM-SSB-WC + 100 AM-SSB-SC clean samples from
clean2a formal12000 (first 100 per class, k=0..99 -> source_index 8500..8599 /
9000..9099; NOT filtered by prediction or confidence), emits the 12 per-sample
raw24 fields required by task book §5 plus seed / source SHA provenance, and the
Phase-A metrics required by §6.

The WC/SC source indices are read from the frozen label contract
(contracts/rml23_merged_contract.py) and asserted — never hard-coded from memory;
if the contract's AM-SSB indices are not (WC=17, SC=18) the script stops (§5).

Reads:
  F:/嵌赛/fix10clean2a_dataset/clean24_formal12000.hdf5
  F:/FPGA_Work/sdr_rml24_npu_deployment_m29/_frozen/.../best.pt
  F:/FPGA_Work/sdr_rml24_npu_deployment_m29/board_rml23_live/{contracts,postprocess}
Writes (under results/amssb_wc_sc/):
  phaseA_per_sample.tsv
  phaseA_summary.json
  phaseA_confusion_raw24.csv        (24x24)
  phaseA_confusion_deployed23.csv   (23x23)
  phaseA_confusion_wc_sc_2x2.csv    (WC/SC focused, with a "to-other" sink)

Deterministic: eval mode, fp32, no shuffling, fixed sample selection.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

# torch lives in the user site-packages (removed by ``python -I``); numpy/h5py
# are in the Anaconda env.  Mirrors the established clean2a pattern.
USER_SITE = r"C:\Users\shado\AppData\Roaming\Python\Python313\site-packages"
if os.path.isdir(USER_SITE) and USER_SITE not in sys.path:
    sys.path.insert(0, USER_SITE)

import numpy as np  # noqa: E402
import h5py  # noqa: E402
import torch  # noqa: E402

MODEL_SRC = r"F:\FPGA_Work\sdr_amr_12class_ood_u_v1"
MERGE_DIR = r"F:\FPGA_Work\sdr_rml24_npu_deployment_m29\board_rml23_live\postprocess"
MERGE_CONTRACT_DIR = r"F:\FPGA_Work\sdr_rml24_npu_deployment_m29\board_rml23_live\contracts"
CHECKPOINT = (r"F:\FPGA_Work\sdr_rml24_npu_deployment_m29\_frozen\runs\rml24_base"
              r"\formal\t002_losscross_entropy_optadamw\seed2027\checkpoints\best.pt")
EXPECTED_CHECKPOINT_SHA = "96cd25f87d6f6f8cacda94432136db9420f74300cecba71df3c9fbe49817be6d"

DATASET = Path(r"F:/嵌赛/fix10clean2a_dataset/clean24_formal12000.hdf5")
EXPECTED_DATASET_SHA = "8b3efe0b11143b31972d392f5b85bc8bd3faf7973681c4d5d7da7ed9603ed81a"
DATASET_SAMPLES_PER_CLASS = 500
DATASET_SEED_BASE = 2_000_000
WC_SAMPLES = 100
SC_SAMPLES = 100

RESULTS_DIR = Path(r"F:/嵌赛/amssb_wc_sc_audit_work/results/amssb_wc_sc")

# model architecture (frozen base config rml24_base.yaml)
MODEL_KWARGS = {
    "denoiser_channels": 24,
    "denoiser_blocks": 3,
    "feature_channels": (32, 48, 64, 96),
    "classifier_hidden": 128,
    "dropout": 0.15,
}
BATCH_SIZE = 512

sys.path.insert(0, MODEL_SRC)
sys.path.insert(0, MERGE_DIR)
sys.path.insert(0, MERGE_CONTRACT_DIR)
from models.ad_amr_v1_1_net import ADAMRV11Net  # noqa: E402
from rml23_merged_contract import (  # noqa: E402
    AMSSB_SOURCE_WC, AMSSB_SOURCE_SC,
    DEPLOYED_LABEL_ORDER_23, SOURCE_LABEL_ORDER_24, SOURCE_TO_DEPLOYED,
    assert_source_order_matches, assert_23class_contract_consistent,
)
from rml23_merged import merge_many_24_to_23  # noqa: E402


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _load_model():
    sha = hashlib.sha256(Path(CHECKPOINT).read_bytes()).hexdigest()
    if sha != EXPECTED_CHECKPOINT_SHA:
        raise SystemExit(f"checkpoint SHA mismatch: got {sha}, expected {EXPECTED_CHECKPOINT_SHA}")
    ck = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    model = ADAMRV11Net(num_classes=24, **MODEL_KWARGS)
    model.load_state_dict(ck["model_state"])
    model.eval()
    return model, ck


def _load_dataset():
    sha = hashlib.sha256(DATASET.read_bytes()).hexdigest()
    if sha != EXPECTED_DATASET_SHA:
        raise SystemExit(f"dataset SHA mismatch: got {sha}, expected {EXPECTED_DATASET_SHA}")
    with h5py.File(DATASET, "r") as f:
        X = f["X"][:]          # [N, 1024, 2] fp32, (t,0)=real (t,1)=imag
        Y = np.asarray(f["Y"]).astype(np.int64)
        seeds = np.asarray(f["seeds"]).astype(np.int64)
        order = json.loads(f.attrs["label_order"])
    assert list(order) == list(SOURCE_LABEL_ORDER_24), "label_order mismatch vs frozen 24-class order"
    # model input is [N,2,1024] planar [real, imag]
    x_in = np.ascontiguousarray(X.transpose(0, 2, 1)).astype(np.float32)
    return X, x_in, Y, seeds


def _select_samples(Y: np.ndarray) -> list[int]:
    """Fixed, confidence-free selection: first 100 WC + first 100 SC.

    formal12000 is stored class-major: row = cidx*samples_per_class + k.
    WC (cidx=17) -> rows [8500, 8600); SC (cidx=18) -> rows [9000, 9100).
    """
    assert (Y == AMSSB_SOURCE_WC).sum() >= WC_SAMPLES, "not enough WC samples"
    assert (Y == AMSSB_SOURCE_SC).sum() >= SC_SAMPLES, "not enough SC samples"
    wc_idx = np.flatnonzero(Y == AMSSB_SOURCE_WC)[:WC_SAMPLES]
    sc_idx = np.flatnonzero(Y == AMSSB_SOURCE_SC)[:SC_SAMPLES]
    sel = np.concatenate([wc_idx, sc_idx])
    assert len(sel) == WC_SAMPLES + SC_SAMPLES
    return [int(i) for i in sel]


def _predict(model, x_in, indices):
    logits_all = np.empty((len(indices), 24), dtype=np.float64)
    with torch.inference_mode():
        for lo in range(0, len(indices), BATCH_SIZE):
            hi = min(lo + BATCH_SIZE, len(indices))
            batch = torch.from_numpy(x_in[indices[lo:hi]])
            out, _ = model(batch)
            logits_all[lo:hi] = out.detach().numpy().astype(np.float64)
    if not np.isfinite(logits_all).all():
        raise SystemExit("non-finite logits produced by model")
    return logits_all


def _confusion(pred, truth, n_classes):
    cm = np.zeros((n_classes, n_classes), dtype=np.int64)
    for p, t in zip(pred.tolist(), truth.tolist()):
        cm[int(t), int(p)] += 1
    return cm


def _top2(logits):
    order = np.argsort(-logits, axis=1)
    return order[:, 0].astype(np.int64), order[:, 1].astype(np.int64)


def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # fail closed before any math: frozen contract must be internally consistent
    # and its WC/SC indices must be exactly 17 / 18 (task book §5).
    assert_23class_contract_consistent()
    assert_source_order_matches(SOURCE_LABEL_ORDER_24)
    if SOURCE_LABEL_ORDER_24[AMSSB_SOURCE_WC] != "AM-SSB-WC" or AMSSB_SOURCE_WC != 17:
        raise SystemExit("contract AM-SSB-WC index is not 17 -- STOP")
    if SOURCE_LABEL_ORDER_24[AMSSB_SOURCE_SC] != "AM-SSB-SC" or AMSSB_SOURCE_SC != 18:
        raise SystemExit("contract AM-SSB-SC index is not 18 -- STOP")

    model, ck = _load_model()
    X, x_in, Y, seeds = _load_dataset()
    sel = _select_samples(Y)
    logits = _predict(model, x_in, sel)

    merged = merge_many_24_to_23(logits)              # (N, 23)
    pred24 = logits.argmax(axis=1)
    top1, top2 = _top2(logits)
    pred23 = merged.argmax(axis=1)
    truth24 = Y[sel]
    truth23 = np.asarray([SOURCE_TO_DEPLOYED[int(y)] for y in truth24], dtype=np.int64)

    wc_logit = logits[:, AMSSB_SOURCE_WC]
    sc_logit = logits[:, AMSSB_SOURCE_SC]
    wc_minus_sc = wc_logit - sc_logit
    raw24_correct = (pred24 == truth24)
    # wc_sc_pair_correct = (WC sample & wc_logit>sc_logit) or (SC sample & sc_logit>wc_logit)
    wc_sc_pair_correct = np.where(
        truth24 == AMSSB_SOURCE_WC, wc_logit > sc_logit, sc_logit > wc_logit)

    # ---- per-sample table (§5 12 fields + seed + source sha) ----
    rows = []
    for n, i in enumerate(sel):
        src_tensor = np.ascontiguousarray(X[i].transpose(1, 0)).astype(np.float32)  # [2,1024]
        rows.append({
            "source_index": int(i),
            "seed": int(seeds[i]),
            "file_name": f"clean24_formal12000.hdf5[{int(i)}]",
            "source_sha256": _sha256_bytes(X[i].tobytes()),
            "input_tensor_sha256": _sha256_bytes(src_tensor.tobytes()),
            "true_raw24_class": int(truth24[n]),
            "raw24_top1": int(top1[n]),
            "raw24_top2": int(top2[n]),
            "wc_logit": float(wc_logit[n]),
            "sc_logit": float(sc_logit[n]),
            "wc_minus_sc_margin": float(wc_minus_sc[n]),
            "raw24_correct": int(raw24_correct[n]),
            "wc_sc_pair_correct": int(wc_sc_pair_correct[n]),
            "deployed23_top1": int(pred23[n]),
        })

    tsv_path = RESULTS_DIR / "phaseA_per_sample.tsv"
    cols = ["source_index", "seed", "file_name", "source_sha256", "input_tensor_sha256",
            "true_raw24_class", "raw24_top1", "raw24_top2", "wc_logit", "sc_logit",
            "wc_minus_sc_margin", "raw24_correct", "wc_sc_pair_correct", "deployed23_top1"]
    with open(tsv_path, "w", encoding="utf-8") as fh:
        fh.write("\t".join(cols) + "\n")
        for r in rows:
            fh.write("\t".join(str(r[c]) for c in cols) + "\n")

    # ---- Phase A metrics (§6) ----
    wc_mask = truth24 == AMSSB_SOURCE_WC
    sc_mask = truth24 == AMSSB_SOURCE_SC
    wc_recall = float(raw24_correct[wc_mask].mean())
    sc_recall = float(raw24_correct[sc_mask].mean())
    balanced_acc = 0.5 * (wc_recall + sc_recall)

    wc_to_sc = int(((wc_mask) & (pred24 == AMSSB_SOURCE_SC)).sum())
    sc_to_wc = int(((sc_mask) & (pred24 == AMSSB_SOURCE_WC)).sum())
    in_am = (pred24 == AMSSB_SOURCE_WC) | (pred24 == AMSSB_SOURCE_SC)
    to_other = int((~in_am).sum())
    pair_correct = int(wc_sc_pair_correct.sum())

    nan_inf = int(np.isnan(logits).sum()) + int(np.isinf(logits).sum())
    excluded = 0

    stable = (wc_recall >= 0.95 and sc_recall >= 0.95 and balanced_acc >= 0.95
              and excluded == 0 and nan_inf == 0)

    # raw24 24x24 + deployed23 23x23 + focused WC/SC 2x2 (with "other" sink)
    cm24 = _confusion(pred24, truth24, 24)
    cm23 = _confusion(pred23, truth23, 23)
    # focused: rows = {WC, SC}, cols = {WC, SC, other}
    cm_wcsc = np.zeros((2, 3), dtype=np.int64)
    for n in range(len(sel)):
        r = 0 if truth24[n] == AMSSB_SOURCE_WC else 1
        if pred24[n] == AMSSB_SOURCE_WC:
            c = 0
        elif pred24[n] == AMSSB_SOURCE_SC:
            c = 1
        else:
            c = 2
        cm_wcsc[r, c] += 1

    summary = {
        "phase": "A",
        "backend": "fp32_pytorch",
        "checkpoint_sha256": EXPECTED_CHECKPOINT_SHA,
        "dataset": str(DATASET),
        "dataset_sha256": EXPECTED_DATASET_SHA,
        "n_wc": int(wc_mask.sum()),
        "n_sc": int(sc_mask.sum()),
        "n_total": int(len(sel)),
        "n_excluded": excluded,
        "nan_inf": nan_inf,
        "selection_rule": "first 100 WC (source_index 8500..8599) + first 100 SC (9000..9099), k=0..99, not confidence-filtered",
        "verdict": "FP32_CLEAN_WC_SC_STABLE" if stable else "FP32_CLEAN_WC_SC_NOT_STABLE",
        "wc_recall": wc_recall,
        "sc_recall": sc_recall,
        "balanced_accuracy": balanced_acc,
        "wc_to_sc": wc_to_sc,
        "sc_to_wc": sc_to_wc,
        "wc_or_sc_to_other": to_other,
        "wc_sc_pair_correct": pair_correct,
        "wc_sc_pair_correct_rate": float(pair_correct / len(sel)),
        "wc_minus_sc_margin": {
            "mean": float(wc_minus_sc.mean()),
            "median": float(np.median(wc_minus_sc)),
            "min": float(wc_minus_sc.min()),
            "max": float(wc_minus_sc.max()),
            "std": float(wc_minus_sc.std()),
            "wc_mean": float(wc_minus_sc[wc_mask].mean()),
            "sc_mean": float(wc_minus_sc[sc_mask].mean()),
        },
        "thresholds": {"wc_recall_ge": 0.95, "sc_recall_ge": 0.95,
                       "balanced_accuracy_ge": 0.95, "excluded_eq": 0, "nan_inf_eq": 0},
        "confusion_matrix_raw24": cm24.tolist(),
        "confusion_matrix_deployed23": cm23.tolist(),
        "confusion_matrix_wc_sc_focused": {"rows": ["WC", "SC"],
                                           "cols": ["WC", "SC", "other"],
                                           "matrix": cm_wcsc.tolist()},
    }
    (RESULTS_DIR / "phaseA_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    np.savetxt(RESULTS_DIR / "phaseA_confusion_raw24.csv", cm24, fmt="%d", delimiter=",")
    np.savetxt(RESULTS_DIR / "phaseA_confusion_deployed23.csv", cm23, fmt="%d", delimiter=",")
    np.savetxt(RESULTS_DIR / "phaseA_confusion_wc_sc_2x2.csv", cm_wcsc, fmt="%d", delimiter=",")

    print(f"== Phase A: FP32 clean WC/SC distinguishability ({len(sel)} samples) ==")
    print(f"verdict       = {summary['verdict']}")
    print(f"WC recall     = {wc_recall:.4f}   (n={wc_mask.sum()})")
    print(f"SC recall     = {sc_recall:.4f}   (n={sc_mask.sum()})")
    print(f"balanced acc  = {balanced_acc:.4f}")
    print(f"WC->SC        = {wc_to_sc}   SC->WC = {sc_to_wc}   to-other = {to_other}")
    print(f"pair_correct  = {pair_correct}/{len(sel)} ({pair_correct/len(sel):.4f})")
    print(f"wc-sc margin  mean={wc_minus_sc.mean():+.4f}  wc_mean={wc_minus_sc[wc_mask].mean():+.4f}  sc_mean={wc_minus_sc[sc_mask].mean():+.4f}")
    print(f"nan/inf       = {nan_inf}   excluded = {excluded}")
    print(f"-> {tsv_path}")
    print(f"-> {RESULTS_DIR / 'phaseA_summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
