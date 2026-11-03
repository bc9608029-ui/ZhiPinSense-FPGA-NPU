"""fix10clean2a Phase 5 — evaluate the frozen 24-class model on CLEAN generated IQ.

This is the definitive acceptance test for the whole task: does the frozen
PyTorch model (checkpoint SHA 96cd25f8..., never retrained) recognise *clean*
(noise-free, no channel, deterministic) IQ constructed in the local RadioML
domain?

Two accounting views, both reported every run:
  * raw24      — argmax over the 24 raw logits vs the 24-class source label.
  * deployed23 — the 24 raw logits are folded to 23 classes with the AM-SSB
                 logaddexp merge (WC+SC -> AM-SSB, the frozen deployment
                 contract), then argmax vs the 23-class deployed label.

Acceptance (§11.1, evaluated on formal12000 = 500/class = 12000):
    raw24      overall >= 0.95 and macro >= 0.95
    deployed23 overall >= 0.95 and macro >= 0.95
    every deployed23 class recall >= 0.90
    formal_scored == 12000, formal_excluded == 0, NaN/Inf == 0

Deterministic: model in eval mode, no dropout, fp32, no data shuffling.  Reads
the frozen checkpoint, the frozen 24-class model (ADAMRV11Net, num_classes=24,
input [N,2,1024] planar [real,imag], no re-scaling), and the clean dataset.

Reads:  dataset/clean24_<set>.hdf5   (Phase 2/3 clean generation)
Writes: results/CLEAN2A_PHASE5_MODEL_EVAL_<set>.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

# torch lives in the user site-packages (removed by ``python -I``); numpy/h5py
# are in the Anaconda env.  This mirrors the established f2 pattern.
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

DATASET_DIR = Path(r"F:/嵌赛/fix10clean2a_dataset")
RESULTS_DIR = Path(r"F:/嵌赛/fix10clean2a_results")

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
    DEPLOYED_LABEL_ORDER_23, SOURCE_LABEL_ORDER_24, SOURCE_TO_DEPLOYED,
    assert_source_order_matches,
)
from rml23_merged import merge_many_24_to_23  # noqa: E402


def _load_model() -> ADAMRV11Net:
    sha = hashlib.sha256(Path(CHECKPOINT).read_bytes()).hexdigest()
    if sha != EXPECTED_CHECKPOINT_SHA:
        raise SystemExit(f"checkpoint SHA mismatch: got {sha}, expected {EXPECTED_CHECKPOINT_SHA}")
    ck = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    model = ADAMRV11Net(num_classes=24, **MODEL_KWARGS)
    model.load_state_dict(ck["model_state"])
    model.eval()
    return model, ck


def _load_dataset(name: str):
    path = DATASET_DIR / f"clean24_{name}.hdf5"
    with h5py.File(path, "r") as f:
        X = f["X"][:]          # [N, 1024, 2] fp32, (t,0)=real (t,1)=imag
        Y = np.asarray(f["Y"]).astype(np.int64)
        seeds = np.asarray(f["seeds"]).astype(np.int64)
        order = json.loads(f.attrs["label_order"])
    # model input is [N,2,1024] planar [real, imag] — no re-scaling (RMS already
    # matches the training domain per class).
    assert list(order) == list(SOURCE_LABEL_ORDER_24), "label_order mismatch vs frozen 24-class order"
    x_in = np.ascontiguousarray(X.transpose(0, 2, 1)).astype(np.float32)
    return x_in, Y, seeds


def _predict(model, x_in):
    logits_all = np.empty((x_in.shape[0], 24), dtype=np.float64)
    with torch.inference_mode():
        for lo in range(0, x_in.shape[0], BATCH_SIZE):
            hi = min(lo + BATCH_SIZE, x_in.shape[0])
            batch = torch.from_numpy(x_in[lo:hi])
            out, _ = model(batch)          # (logits, denoised)
            logits_all[lo:hi] = out.detach().numpy().astype(np.float64)
    if not np.isfinite(logits_all).all():
        raise SystemExit("non-finite logits produced by model")
    return logits_all


def _raw24_metrics(logits, Y):
    pred = logits.argmax(axis=1)
    correct = pred == Y
    overall = float(correct.mean())
    recalls = {}
    for c in range(24):
        m = Y == c
        recalls[SOURCE_LABEL_ORDER_24[c]] = float(correct[m].mean()) if m.any() else float("nan")
    macro = float(np.mean([r for r in recalls.values() if not np.isnan(r)]))
    return {"overall": overall, "macro": macro, "per_class_recall": recalls,
            "per_class_count": {c: int((Y == i).sum()) for i, c in enumerate(SOURCE_LABEL_ORDER_24)}}


def _deployed23_metrics(logits, Y):
    merged = merge_many_24_to_23(logits)   # (N, 23) logaddexp-folded
    pred = merged.argmax(axis=1)
    truth = np.asarray([SOURCE_TO_DEPLOYED[int(y)] for y in Y], dtype=np.int64)
    correct = pred == truth
    overall = float(correct.mean())
    recalls = {}
    counts = {}
    for d in range(23):
        m = truth == d
        recalls[DEPLOYED_LABEL_ORDER_23[d]] = float(correct[m].mean()) if m.any() else float("nan")
        counts[DEPLOYED_LABEL_ORDER_23[d]] = int(m.sum())
    macro = float(np.mean([r for r in recalls.values() if not np.isnan(r)]))
    min_recall = float(np.nanmin(list(recalls.values())))
    return {"overall": overall, "macro": macro, "min_recall": min_recall,
            "per_class_recall": recalls, "per_class_count": counts}


def _confusion(pred: np.ndarray, truth: np.ndarray, n_classes: int) -> list[list[int]]:
    cm = np.zeros((n_classes, n_classes), dtype=np.int64)
    for p, t in zip(pred.tolist(), truth.tolist()):
        cm[int(t), int(p)] += 1
    return cm.tolist()


def _top2_accuracy(logits: np.ndarray, truth: np.ndarray) -> float:
    # top-2 correct == true class is within the two highest logits
    order = np.argsort(-logits, axis=1)               # (N, 24) descending
    top2 = order[:, :2]
    return float(np.mean(np.any(top2 == truth[:, None], axis=1)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="smoke96", choices=["smoke96", "dev2400", "formal12000"])
    args = ap.parse_args()

    # fail closed before any math: the frozen 24-class order must hash-match
    assert_source_order_matches(SOURCE_LABEL_ORDER_24)

    model, ck = _load_model()
    x_in, Y, seeds = _load_dataset(args.set)
    logits = _predict(model, x_in)

    raw24 = _raw24_metrics(logits, Y)
    dep23 = _deployed23_metrics(logits, Y)

    merged = merge_many_24_to_23(logits)              # (N, 23)
    pred24 = logits.argmax(axis=1)
    pred23 = merged.argmax(axis=1)
    truth23 = np.asarray([SOURCE_TO_DEPLOYED[int(y)] for y in Y], dtype=np.int64)

    # per-sample top1/top2/margin + predictions (deployed23 truth/pred per §10)
    order = np.argsort(-logits, axis=1)
    top1_logit = logits[np.arange(len(Y)), order[:, 0]]
    top2_logit = logits[np.arange(len(Y)), order[:, 1]]
    margin = top1_logit - top2_logit

    nan_inf = int(np.isnan(logits).sum()) + int(np.isinf(logits).sum())
    result = {
        "set": args.set,
        "n_samples": int(len(Y)),
        "n_excluded": 0,
        "nan_inf": nan_inf,
        "checkpoint_sha256": EXPECTED_CHECKPOINT_SHA,
        "best_epoch": ck.get("best_epoch"),
        "best_selection_score": ck.get("best_selection_score"),
        "top2_accuracy_raw24": _top2_accuracy(logits, Y),
        "top2_accuracy_deployed23": _top2_accuracy(merged, truth23),
        "margin": {
            "mean": float(margin.mean()),
            "median": float(np.median(margin)),
            "min": float(margin.min()),
            "max": float(margin.max()),
        },
        "confusion_matrix_raw24": _confusion(pred24, Y, 24),
        "confusion_matrix_deployed23": _confusion(pred23, truth23, 23),
        "raw24": raw24,
        "deployed23": dep23,
    }
    out = RESULTS_DIR / f"CLEAN2A_PHASE5_MODEL_EVAL_{args.set}.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")

    # per-sample predictions TSV (deterministic row order == dataset order)
    tsv = RESULTS_DIR / f"frozen_model_predictions_{args.set}.tsv"
    with open(tsv, "w", encoding="utf-8") as fh:
        fh.write("sample_id\traw24_label\tdeployed23_label\traw24_pred\tdeployed23_pred\t"
                 "top1_logit\ttop2_logit\tmargin\tcorrect_raw24\tcorrect_deployed23\n")
        for i in range(len(Y)):
            fh.write(f"{i}\t{SOURCE_LABEL_ORDER_24[int(Y[i])]}\t"
                     f"{DEPLOYED_LABEL_ORDER_23[int(truth23[i])]}\t"
                     f"{SOURCE_LABEL_ORDER_24[int(pred24[i])]}\t"
                     f"{DEPLOYED_LABEL_ORDER_23[int(pred23[i])]}\t"
                     f"{top1_logit[i]:.6f}\t{top2_logit[i]:.6f}\t{margin[i]:.6f}\t"
                     f"{int(pred24[i] == Y[i])}\t{int(pred23[i] == truth23[i])}\n")

    # confusion-matrix CSVs
    np.savetxt(RESULTS_DIR / f"confusion_matrix_raw24_{args.set}.csv",
               np.asarray(result["confusion_matrix_raw24"]), fmt="%d", delimiter=",")
    np.savetxt(RESULTS_DIR / f"confusion_matrix_deployed23_{args.set}.csv",
               np.asarray(result["confusion_matrix_deployed23"]), fmt="%d", delimiter=",")

    # console summary
    print(f"== Phase 5 frozen-model eval on clean24_{args.set} ({len(Y)} samples) ==")
    print(f"checkpoint best_epoch={ck.get('best_epoch')} "
          f"best_selection_score={ck.get('best_selection_score')}  nan_inf={nan_inf}")
    print(f"raw24      overall={raw24['overall']:.4f}  macro={raw24['macro']:.4f}  "
          f"top2={result['top2_accuracy_raw24']:.4f}")
    print(f"deployed23 overall={dep23['overall']:.4f}  macro={dep23['macro']:.4f}  "
          f"min_recall={dep23['min_recall']:.4f}")
    print("\nraw24 per-class recall:")
    for c in SOURCE_LABEL_ORDER_24:
        print(f"  {c:<10} {raw24['per_class_recall'][c]:.4f}  (n={raw24['per_class_count'][c]})")
    print("\ndeployed23 per-class recall:")
    for c in DEPLOYED_LABEL_ORDER_23:
        print(f"  {c:<10} {dep23['per_class_recall'][c]:.4f}  (n={dep23['per_class_count'][c]})")
    print(f"\n-> {out}")
    print(f"-> {tsv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
