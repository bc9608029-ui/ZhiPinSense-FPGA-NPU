#!/usr/bin/env python3
"""Strict two-session retraining check for the 480 captured real-RF tensors.

This is a diagnostic, not a final model-selection protocol.  Each fold uses one
session only for development (8 train + 2 validation examples per class) and
touches the other session once for the reported cross-session test metric.
Both random initialization and the frozen RadioML initialization are tested.
No digital samples are included in the training set.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import random
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
WORK_ROOT = HERE.parents[1]
TRAIN_PATH = HERE / "train_finetune_pilot.py"


def load_train_module():
    spec = importlib.util.spec_from_file_location("pilot1_train_480", TRAIN_PATH)
    if spec is None or spec.loader is None:
        raise SystemExit("cannot load %s" % TRAIN_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.LINE_A = WORK_ROOT / "line_a"
    return mod


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_rf_records(T, tsv: Path, tensor_dir: Path, session: str, gt):
    all_records = T.build_finetune_dataset(
        tsv, tensor_dir, session, "RF_ALL_FINITE", gt=gt)
    records = [r for r in all_records if r[2]]
    if len(records) != 240:
        raise SystemExit("%s RF records=%d (want 240)" % (session, len(records)))
    counts = np.bincount(np.asarray([r[1] for r in records]), minlength=24)
    if counts.tolist() != [10] * 24:
        raise SystemExit("%s class counts invalid: %s" % (session, counts.tolist()))
    for p, _, _ in records:
        if p.stat().st_size != 8192:
            raise SystemExit("bad tensor size: %s" % p)
    return records


def stratified_dev_split(records, seed: int):
    rng = random.Random(seed)
    by_class = {c: [] for c in range(24)}
    for rec in records:
        by_class[rec[1]].append(rec)
    train, val = [], []
    for c in range(24):
        rows = sorted(by_class[c], key=lambda r: r[0].name)
        rng.shuffle(rows)
        train.extend(rows[:8])
        val.extend(rows[8:])
    rng.shuffle(train)
    rng.shuffle(val)
    return train, val


def make_model(T, init: str):
    torch, nn, Net = T._load_torch_and_model()
    if init == "pretrained":
        model = T.load_frozen_model()[3]
    elif init == "random":
        torch.manual_seed(0)
        model = Net(num_classes=T.N_CLASSES, **T.MODEL_KWARGS)
    else:
        raise ValueError(init)
    for p in model.parameters():
        p.requires_grad = True
    return torch, nn, model


def load_batch(T, torch, records, idxs, augment: bool, rng):
    x, y = T._load_batch(torch, records, idxs)
    if augment:
        # A global complex rotation and modest scale/noise are label preserving
        # RF-channel perturbations.  Apply only to the training batch.
        b = x.shape[0]
        theta = torch.from_numpy(rng.uniform(-math.pi, math.pi, size=b).astype(np.float32))
        scale = torch.from_numpy(rng.uniform(0.85, 1.15, size=b).astype(np.float32))
        cs, sn = torch.cos(theta) * scale, torch.sin(theta) * scale
        i, q = x[:, 0].clone(), x[:, 1].clone()
        x[:, 0] = cs[:, None] * i - sn[:, None] * q
        x[:, 1] = sn[:, None] * i + cs[:, None] * q
        rms = torch.sqrt(torch.mean(x * x, dim=(1, 2), keepdim=True) + 1e-12)
        sigma = torch.from_numpy(rng.uniform(0.0, 0.015, size=b).astype(np.float32))
        x = x + torch.randn_like(x) * rms * sigma[:, None, None]
    return x, y


def evaluate(T, torch, model, records):
    model.eval()
    truth, pred = [], []
    with torch.no_grad():
        for start in range(0, len(records), 64):
            idx = list(range(start, min(start + 64, len(records))))
            x, y = T._load_batch(torch, records, idx)
            logits, _ = model(x)
            truth.extend(y.numpy().tolist())
            pred.extend(logits.argmax(1).numpy().tolist())
    conf = np.zeros((24, 24), dtype=np.int64)
    for y, p in zip(truth, pred):
        conf[y, p] += 1
    recalls = []
    for c in range(24):
        den = int(conf[c].sum())
        recalls.append(float(conf[c, c] / den) if den else 0.0)
    counts = np.bincount(np.asarray(pred, dtype=np.int64), minlength=24)
    return {
        "n": len(truth),
        "accuracy": float(np.trace(conf) / len(truth)),
        "macro_recall": float(np.mean(recalls)),
        "classes_recall_ge_0_7": int(sum(r >= 0.7 for r in recalls)),
        "classes_recall_ge_0_8": int(sum(r >= 0.8 for r in recalls)),
        "distinct_predicted_classes": int(np.count_nonzero(counts)),
        "largest_prediction_share": float(counts.max() / len(pred)),
        "per_class_recall": recalls,
        "confusion_matrix": conf.tolist(),
    }


def train_one(T, init: str, train_records, val_records, test_records,
              seed: int, epochs: int, patience: int, lr: float,
              weight_decay: float, augment: bool, out_dir: Path, tag: str):
    torch, nn, model = make_model(T, init)
    torch.manual_seed(seed)
    np_rng = np.random.default_rng(seed)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    loss_fn = nn.CrossEntropyLoss(label_smoothing=0.05)
    best = -1.0
    best_state = None
    best_epoch = -1
    bad = 0
    curve = []
    batch_size = 32
    for epoch in range(epochs):
        model.train()
        order = np_rng.permutation(len(train_records)).tolist()
        correct = total = 0
        losses = []
        for start in range(0, len(order), batch_size):
            idx = order[start:start + batch_size]
            x, y = load_batch(T, torch, train_records, idx, augment, np_rng)
            opt.zero_grad(set_to_none=True)
            logits, _ = model(x)
            loss = loss_fn(logits, y)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            losses.append(float(loss.detach()))
            correct += int((logits.argmax(1) == y).sum())
            total += int(y.numel())
        val = evaluate(T, torch, model, val_records)
        row = {"epoch": epoch, "loss": float(np.mean(losses)),
               "train_accuracy": correct / total, "val_accuracy": val["accuracy"]}
        curve.append(row)
        if val["accuracy"] > best:
            best = val["accuracy"]
            best_epoch = epoch
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
            bad = 0
        else:
            bad += 1
        if epoch % 10 == 0 or bad == 0 or bad >= patience:
            print("%s epoch=%d loss=%.4f train=%.4f val=%.4f best=%.4f" %
                  (tag, epoch, row["loss"], row["train_accuracy"],
                   row["val_accuracy"], best), flush=True)
        if bad >= patience:
            break
    if best_state is None:
        raise SystemExit("no best state")
    model.load_state_dict(best_state)
    ckpt = out_dir / (tag + ".pt")
    torch.save({"model_state": model.state_dict(), "tag": tag,
                "best_internal_val_accuracy": best, "best_epoch": best_epoch}, ckpt)
    return {
        "init": init,
        "seed": seed,
        "augment": augment,
        "lr": lr,
        "train_n": len(train_records),
        "internal_val_n": len(val_records),
        "cross_session_test_n": len(test_records),
        "best_epoch": best_epoch,
        "best_internal_val_accuracy": best,
        "train_metrics": evaluate(T, torch, model, train_records),
        "internal_val_metrics": evaluate(T, torch, model, val_records),
        "cross_session_test_metrics": evaluate(T, torch, model, test_records),
        "curve": curve,
        "checkpoint": str(ckpt),
        "checkpoint_sha256": sha256(ckpt),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    cap = WORK_ROOT / "board_captures" / "extracted_S1_S2_20261022"
    ap.add_argument("--s1-dir", default=str(cap / "pilot1_capture_S1_1773375833_213"))
    ap.add_argument("--s2-dir", default=str(cap / "pilot1_capture_S2_1773384577_213"))
    ap.add_argument("--ground-truth", default=str(WORK_ROOT / "line_a" / "results" /
                                                    "source_manifest_960.tsv"))
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--seeds", default="2027")
    ap.add_argument("--inits", default="random,pretrained")
    ap.add_argument("--folds", default="S1_to_S2,S2_to_S1")
    ap.add_argument("--epochs", type=int, default=120)
    ap.add_argument("--patience", type=int, default=20)
    ap.add_argument("--augment", action="store_true")
    args = ap.parse_args()

    T = load_train_module()
    gt = T.load_ground_truth(Path(args.ground_truth))
    s1_dir, s2_dir = Path(args.s1_dir), Path(args.s2_dir)
    s1 = load_rf_records(T, s1_dir / "capture_results_S1.tsv", s1_dir, "S1", gt)
    s2 = load_rf_records(T, s2_dir / "capture_results_S2.tsv", s2_dir, "S2", gt)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    sessions = {"S1": s1, "S2": s2}
    report = {
        "status": "STRICT_480_REALRF_RETRAIN_DIAGNOSTIC",
        "protocol": "one session development with stratified 8/2 per class; other session untouched test",
        "digital_samples_used": 0,
        "runs": [],
    }
    for fold in [x for x in args.folds.split(",") if x]:
        train_name, test_name = fold.split("_to_")
        for seed in [int(x) for x in args.seeds.split(",") if x]:
            dev_train, dev_val = stratified_dev_split(sessions[train_name], seed)
            for init in [x for x in args.inits.split(",") if x]:
                lr = 1e-3 if init == "random" else 1e-4
                tag = "%s_%s_seed%d%s" % (
                    fold, init, seed, "_aug" if args.augment else "")
                result = train_one(T, init, dev_train, dev_val, sessions[test_name],
                                   seed, args.epochs, args.patience, lr, 1e-4,
                                   args.augment, out, tag)
                result["fold"] = fold
                report["runs"].append(result)
                (out / "retrain_480_partial.json").write_text(
                    json.dumps(report, indent=2) + "\n", encoding="utf-8")
                m = result["cross_session_test_metrics"]
                print("RETRAIN480_RESULT tag=%s test_acc=%.4f macro=%.4f classes70=%d "
                      "distinct=%d max_share=%.4f" %
                      (tag, m["accuracy"], m["macro_recall"],
                       m["classes_recall_ge_0_7"], m["distinct_predicted_classes"],
                       m["largest_prediction_share"]), flush=True)
    (out / "retrain_480_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("RETRAIN480_DONE report=%s" % (out / "retrain_480_report.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
