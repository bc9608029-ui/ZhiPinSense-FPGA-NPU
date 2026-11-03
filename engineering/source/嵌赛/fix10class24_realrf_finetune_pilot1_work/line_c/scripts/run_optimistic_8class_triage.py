#!/usr/bin/env python3
"""Optimistic upper-bound: retrain an 8-way head on S1, validate on S2.

The eight classes were selected after inspecting the S2 24-way E1 result.  Therefore
this is deliberately optimistic/leaky and cannot be reported as final performance.
Its only valid use is one-sided: if even this upper bound is poor, the 8-class rescue
route is not promising; if it is good, S3 is required for an honest confirmation.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
WORK_ROOT = HERE.parents[1]
TRAIN_PATH = HERE / "train_finetune_pilot.py"
# Post-hoc top eight from the best 24-way S2 E1 run.  Frozen for this single test.
SELECTED = (21, 17, 18, 2, 3, 20, 15, 19)


def load_train_module():
    spec = importlib.util.spec_from_file_location("pilot1_train8", TRAIN_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.LINE_A = WORK_ROOT / "line_a"
    return mod


def make_model(T, torch, nn):
    model = T.load_frozen_model()[3]
    old = model.classifier[3]
    new = nn.Linear(old.in_features, len(SELECTED), bias=True)
    with torch.no_grad():
        new.weight.copy_(old.weight[list(SELECTED)])
        new.bias.copy_(old.bias[list(SELECTED)])
    model.classifier[3] = new
    return model


def freeze(model, exp):
    for p in model.parameters():
        p.requires_grad = False
    if exp == "E1":
        mods = [model.classifier]
    elif exp == "E2":
        mods = [model.features[-1], model.classifier]
    elif exp == "E3":
        mods = [model]
    else:
        raise ValueError(exp)
    for mod in mods:
        for p in mod.parameters():
            p.requires_grad = True


def remap(records):
    mp = {old: new for new, old in enumerate(SELECTED)}
    return [(p, mp[y], rf) for p, y, rf in records if y in mp]


def eval_model(T, model, torch, records):
    model.eval()
    conf = np.zeros((8, 8), dtype=np.int64)
    with torch.no_grad():
        for i in range(0, len(records), 64):
            idx = list(range(i, min(i + 64, len(records))))
            x, y = T._load_batch(torch, records, idx)
            logits, _ = model(x)
            pred = logits.argmax(1)
            for yy, pp in zip(y.tolist(), pred.tolist()):
                conf[yy, pp] += 1
    recall = [float(conf[i, i] / conf[i].sum()) for i in range(8)]
    return {"n": int(conf.sum()), "accuracy": float(np.trace(conf) / conf.sum()),
            "macro_recall": float(np.mean(recall)), "recall": recall,
            "confusion_matrix": conf.tolist()}


def train_one(T, torch, nn, exp, train, val, out, epochs, patience):
    torch.manual_seed(2027)
    rng = np.random.default_rng(2027)
    model = make_model(T, torch, nn)
    freeze(model, exp)
    head = [p for p in model.classifier.parameters() if p.requires_grad]
    if exp == "E1":
        groups = [{"params": head, "lr": 3e-3}]
    elif exp == "E2":
        bone = [p for p in model.features[-1].parameters() if p.requires_grad]
        groups = [{"params": head, "lr": 3e-3}, {"params": bone, "lr": 1e-4}]
    else:
        groups = [{"params": [p for p in model.parameters() if p.requires_grad],
                   "lr": 1e-4}]
    opt = torch.optim.AdamW(groups, weight_decay=1e-4)
    loss_fn = nn.CrossEntropyLoss(label_smoothing=0.1)
    best, best_state, bad, curve = -1.0, None, 0, []
    for ep in range(epochs):
        model.train()
        ok = total = 0
        for idx in T._mixed_batches(train, 32, rng):
            x, y = T._load_batch(torch, train, idx)
            opt.zero_grad()
            logits, _ = model(x)
            loss = loss_fn(logits, y)
            loss.backward()
            opt.step()
            ok += int((logits.argmax(1) == y).sum())
            total += y.numel()
        vm = eval_model(T, model, torch, val)
        curve.append({"epoch": ep, "train_acc": ok / total, "val_acc": vm["accuracy"]})
        print("[%s-8] epoch=%d train=%.4f S2=%.4f best=%.4f" %
              (exp, ep, ok / total, vm["accuracy"], max(best, vm["accuracy"])))
        if vm["accuracy"] > best:
            best = vm["accuracy"]
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
            bad = 0
        else:
            bad += 1
        if bad >= patience:
            break
    model.load_state_dict(best_state)
    s1 = eval_model(T, model, torch, [r for r in train if r[2]])
    s2 = eval_model(T, model, torch, val)
    torch.save({"model_state": model.state_dict(), "selected_original_classes": SELECTED,
                "experiment": exp}, out / (exp + "_8class_best.pt"))
    return {"best_s2_accuracy": best, "s1_rf": s1, "s2_rf": s2, "curve": curve}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--s1-tsv", required=True)
    ap.add_argument("--s1-dir", required=True)
    ap.add_argument("--s2-tsv", required=True)
    ap.add_argument("--s2-dir", required=True)
    ap.add_argument("--ground-truth", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--epochs", type=int, default=50)
    ap.add_argument("--patience", type=int, default=10)
    args = ap.parse_args()
    T = load_train_module()
    torch, nn, _, _, _ = T.load_frozen_model()
    gt = T.load_ground_truth(Path(args.ground_truth))
    train = remap(T.build_finetune_dataset(Path(args.s1_tsv), Path(args.s1_dir),
                                           "S1", "RF_ALL_FINITE", gt=gt))
    val = remap(T.build_finetune_dataset(Path(args.s2_tsv), Path(args.s2_dir),
                                         "S2", "RF_ALL_FINITE", gt=gt))
    val = [r for r in val if r[2]]
    if (sum(r[2] for r in train), sum(not r[2] for r in train), len(val)) != (80, 80, 80):
        raise SystemExit("8-class counts invalid")
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    report = {"status": "OPTIMISTIC_POSTHOC_S2_SELECTED_NOT_FINAL",
              "selected_original_indices": list(SELECTED),
              "selected_names": [T.LABEL_ORDER_24[i] for i in SELECTED],
              "experiments": {}}
    for exp in ("E1", "E2", "E3"):
        report["experiments"][exp] = train_one(
            T, torch, nn, exp, train, val, out, args.epochs, args.patience)
        (out / "optimistic_8class_partial.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (out / "optimistic_8class_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("OPTIMISTIC_8CLASS_DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
