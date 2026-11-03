#!/usr/bin/env python3
"""Time-boxed S1-train/S2-validation finetune triage.

This is deliberately separate from the frozen four-session protocol.  It answers
only whether there is enough independent-session signal to justify collecting S3/S4.
S2 is used for early stopping here, so these numbers are optimistic and MUST NOT be
reported as final test performance.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
from collections import Counter
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
WORK_ROOT = HERE.parents[1]
TRAIN_PATH = HERE / "train_finetune_pilot.py"


def load_train_module():
    spec = importlib.util.spec_from_file_location("pilot1_train", TRAIN_PATH)
    if spec is None or spec.loader is None:
        raise SystemExit("cannot load %s" % TRAIN_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # Enforce the checkout-relative path even if an older train script is used.
    mod.LINE_A = WORK_ROOT / "line_a"
    return mod


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def verify_capture(tsv: Path, tensor_dir: Path, session: str) -> dict:
    with tsv.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    if len(rows) != 240:
        raise SystemExit("%s rows=%d (want 240)" % (session, len(rows)))
    seen = set()
    finite = gate = hard = 0
    classes = Counter()
    for row in rows:
        sid = row["source_id"]
        if sid in seen:
            raise SystemExit("%s duplicate source_id %s" % (session, sid))
        seen.add(sid)
        if not sid.startswith(session.lower() + "_"):
            raise SystemExit("%s has foreign source_id %s" % (session, sid))
        if row["hard_invalid"] == "1":
            hard += 1
        if row["gate_pass"] == "1":
            gate += 1
        declared = row["model_input_sha256"]
        if declared:
            p = tensor_dir / (sid + ".model_input.bin")
            if not p.is_file():
                raise SystemExit("%s missing %s" % (session, p.name))
            if p.stat().st_size != 8192:
                raise SystemExit("%s size=%d (want 8192)" % (p, p.stat().st_size))
            got = sha256(p)
            if got != declared:
                raise SystemExit("%s SHA mismatch %s" % (session, sid))
            finite += 1
        # Source IDs are frozen as sN_cCC_iII; this is an identity audit only,
        # never used as the training label (labels come from host ground truth).
        try:
            classes[int(sid.split("_")[1][1:])] += 1
        except (IndexError, ValueError):
            raise SystemExit("bad source_id format %s" % sid)
    if sorted(classes) != list(range(24)) or any(classes[c] != 10 for c in range(24)):
        raise SystemExit("%s class identity balance invalid: %s" % (session, dict(classes)))
    return {"rows": len(rows), "finite": finite, "gate_pass": gate,
            "hard_invalid": hard, "tensor_sha_ok": finite,
            "identity_count_per_class": dict(sorted(classes.items()))}


def predict(model, torch, train_mod, recs):
    model.eval()
    truth, pred = [], []
    with torch.no_grad():
        for i in range(0, len(recs), 64):
            idx = list(range(i, min(i + 64, len(recs))))
            x, y = train_mod._load_batch(torch, recs, idx)
            logits, _ = model(x)
            truth.extend(y.numpy().tolist())
            pred.extend(logits.argmax(dim=1).numpy().tolist())
    return truth, pred


def metrics(truth, pred, labels):
    conf = np.zeros((24, 24), dtype=np.int64)
    for y, p in zip(truth, pred):
        conf[y, p] += 1
    per_class = []
    for c in range(24):
        n = int(conf[c].sum())
        ok = int(conf[c, c])
        per_class.append({"class_index": c, "class_name": labels[c],
                          "n": n, "correct": ok,
                          "recall": (ok / n) if n else 0.0})
    ordered = sorted(per_class, key=lambda x: (-x["recall"], x["class_index"]))
    pred_counts = np.bincount(np.asarray(pred, dtype=np.int64), minlength=24)
    return {
        "n": len(truth),
        "accuracy": float(np.trace(conf) / len(truth)) if truth else 0.0,
        "macro_recall": float(np.mean([x["recall"] for x in per_class])),
        "distinct_predicted_classes": int(np.count_nonzero(pred_counts)),
        "largest_prediction_share": float(pred_counts.max() / len(pred)) if pred else 0.0,
        "classes_recall_ge_0_7": [x["class_name"] for x in per_class if x["recall"] >= 0.7],
        "classes_recall_ge_0_8": [x["class_name"] for x in per_class if x["recall"] >= 0.8],
        "top8_posthoc_macro_recall": float(np.mean([x["recall"] for x in ordered[:8]])),
        "top8_posthoc_classes": [x["class_name"] for x in ordered[:8]],
        "per_class": per_class,
        "confusion_matrix": conf.tolist(),
    }


def load_checkpoint_model(train_mod, torch, path: Path):
    model = train_mod.load_frozen_model()[3]
    ck = torch.load(path, map_location="cpu", weights_only=False)
    model.load_state_dict(ck["model_state"])
    return model


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--s1-tsv", required=True)
    ap.add_argument("--s1-dir", required=True)
    ap.add_argument("--s2-tsv", required=True)
    ap.add_argument("--s2-dir", required=True)
    ap.add_argument("--ground-truth", default=str(WORK_ROOT / "line_a" / "results" /
                                                    "source_manifest_960.tsv"))
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--experiments", default="E1,E2,E3")
    ap.add_argument("--seed", type=int, default=2027)
    ap.add_argument("--epochs", type=int, default=20)
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--patience", type=int, default=4)
    ap.add_argument("--head-lr", type=float, default=3e-4)
    ap.add_argument("--bone-lr", type=float, default=1e-5)
    args = ap.parse_args()

    s1_tsv, s1_dir = Path(args.s1_tsv), Path(args.s1_dir)
    s2_tsv, s2_dir = Path(args.s2_tsv), Path(args.s2_dir)
    audit = {"S1": verify_capture(s1_tsv, s1_dir, "S1"),
             "S2": verify_capture(s2_tsv, s2_dir, "S2")}

    T = load_train_module()
    torch, nn, _, baseline, _ = T.load_frozen_model()
    gt = T.load_ground_truth(Path(args.ground_truth))
    train = T.build_finetune_dataset(s1_tsv, s1_dir, "S1", "RF_ALL_FINITE", gt=gt)
    train_rf = [r for r in train if r[2]]
    s2_all = T.build_finetune_dataset(s2_tsv, s2_dir, "S2", "RF_ALL_FINITE", gt=gt)
    val_rf = [r for r in s2_all if r[2]]
    n_train_rf = sum(1 for r in train if r[2])
    n_train_dig = sum(1 for r in train if not r[2])
    if (n_train_rf, n_train_dig, len(val_rf)) != (240, 240, 240):
        raise SystemExit("dataset counts invalid: train_rf=%d train_digital=%d val_rf=%d" %
                         (n_train_rf, n_train_dig, len(val_rf)))

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    report = {
        "status": "EARLY_TRIAGE_ONLY_S2_USED_FOR_EARLY_STOPPING_NOT_FINAL_TEST",
        "audit": audit,
        "dataset": {"train_session": "S1", "validation_session": "S2",
                    "train_rf": n_train_rf, "train_digital": n_train_dig,
                    "validation_rf": len(val_rf)},
        "experiments": {},
    }

    y, p = predict(baseline, torch, T, val_rf)
    report["experiments"]["E0"] = metrics(y, p, T.LABEL_ORDER_24)
    y_train, p_train = predict(baseline, torch, T, train_rf)
    report["experiments"]["E0"]["s1_train_rf"] = metrics(
        y_train, p_train, T.LABEL_ORDER_24)
    (out / "early_triage_partial.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("EARLY_TRIAGE E0 S2_RF accuracy=%.4f distinct=%d max_share=%.4f" %
          (report["experiments"]["E0"]["accuracy"],
           report["experiments"]["E0"]["distinct_predicted_classes"],
           report["experiments"]["E0"]["largest_prediction_share"]))

    for exp in [x for x in args.experiments.split(",") if x]:
        meta = T.run_training(exp, args.seed, train, val_rf, out,
                              epochs=args.epochs, batch_size=args.batch_size,
                              head_lr=args.head_lr, bone_lr=args.bone_lr,
                              patience=args.patience, torch=torch, nn=nn)
        model = load_checkpoint_model(T, torch, Path(meta["checkpoint"]))
        y, p = predict(model, torch, T, val_rf)
        m = metrics(y, p, T.LABEL_ORDER_24)
        y_train, p_train = predict(model, torch, T, train_rf)
        m["s1_train_rf"] = metrics(y_train, p_train, T.LABEL_ORDER_24)
        m["best_epoch_validation_accuracy"] = meta["best_val_acc"]
        m["checkpoint"] = meta["checkpoint"]
        m["checkpoint_sha256"] = meta["checkpoint_sha256"]
        report["experiments"][exp] = m
        (out / "early_triage_partial.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print("EARLY_TRIAGE %s S2_RF accuracy=%.4f distinct=%d max_share=%.4f "
              "classes_recall_ge_0_7=%d" %
              (exp, m["accuracy"], m["distinct_predicted_classes"],
               m["largest_prediction_share"], len(m["classes_recall_ge_0_7"])))

    (out / "early_triage_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("EARLY_TRIAGE_DONE report=%s" % (out / "early_triage_report.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
