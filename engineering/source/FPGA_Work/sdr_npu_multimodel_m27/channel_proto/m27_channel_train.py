"""M27 channel/interference synthetic prototype — training + evaluation (spec §十一).

Trains the tiny NPU-supported CNN on *synthetic* data (train/validation/final-test
generated from three disjoint seed streams), then reports the per-environment
confusion matrix and per-SNR accuracy on the held-out final test split.  The trained
checkpoint is a *synthetic prototype*, exported to ONNX and int8-feasibility-checked.
Status is fixed to ``CHANNEL_IMPAIRMENT_MODEL_SYNTHETIC_PROTOTYPE`` — never real
wireless environment recognition.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import torch
import torch.nn.functional as F

from m27_channel_contract import (
    CHANNEL_LABELS,
    ALLOWED_STATUS,
    SUPPORTED_OPS,
)
from m27_channel_generator import generate_all
from m27_channel_model import ChannelImpairmentNet, export_onnx, int8_feasibility


def train(model, x, y, epochs, lr=1e-3, batch=64, device="cpu"):
    model.to(device)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    xt = torch.from_numpy(x).to(device)
    yt = torch.from_numpy(y).to(device)
    n = xt.shape[0]
    for _ in range(epochs):
        model.train()
        perm = torch.randperm(n)
        for i in range(0, n, batch):
            idx = perm[i:i + batch]
            out = model(xt[idx])
            loss = F.cross_entropy(out, yt[idx])
            opt.zero_grad()
            loss.backward()
            opt.step()
    return model


def evaluate(model, x, y, snr, device="cpu"):
    model.eval()
    xt = torch.from_numpy(x).to(device)
    with torch.no_grad():
        logits = model(xt)
        pred = torch.argmax(logits, dim=1).cpu().numpy()
    acc = float((pred == y).mean())

    # per-environment confusion matrix (counts)
    n_labels = len(CHANNEL_LABELS)
    cm = np.zeros((n_labels, n_labels), dtype=np.int64)
    for t, p in zip(y, pred):
        cm[t, p] += 1

    # per-SNR accuracy (low < 10 dB, high >= 10 dB)
    low = snr < 10.0
    per_snr = {
        "low_snr_acc": float((pred[low] == y[low]).mean()) if low.any() else None,
        "high_snr_acc": float((pred[~low] == y[~low]).mean()) if (~low).any() else None,
    }
    return acc, cm, per_snr, pred


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--samples-per-label", type=int, default=64)
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--out", default="m27_channel_artifacts")
    args = ap.parse_args()

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    os.makedirs(args.out, exist_ok=True)

    splits = generate_all(seed=args.seed, samples_per_label=args.samples_per_label)
    xtr, ytr, _ = splits["train"]
    xva, yva, _ = splits["validation"]
    xte, yte, snr_te = splits["final_test"]

    model = ChannelImpairmentNet()
    model = train(model, xtr, ytr, epochs=args.epochs)

    val_acc, _, _, _ = evaluate(model, xva, yva, np.zeros_like(yva, dtype=np.float32))
    te_acc, cm, per_snr, pred = evaluate(model, xte, yte, snr_te)

    onnx_path = os.path.join(args.out, "m27_channel_prototype.onnx")
    export_onnx(model, onnx_path)
    ok_int8, unsupported = int8_feasibility(onnx_path, SUPPORTED_OPS)

    report = {
        "status": ALLOWED_STATUS,
        "seed": args.seed,
        "epochs": args.epochs,
        "validation_accuracy": float(val_acc),
        "final_test_accuracy": float(te_acc),
        "per_snr_accuracy": per_snr,
        "confusion_matrix": cm.tolist(),
        "onnx": onnx_path,
        "int8_feasible": bool(ok_int8),
        "unsupported_ops": unsupported,
        "note": "synthetic prototype only; NOT real wireless environment recognition",
    }
    report_path = os.path.join(args.out, "m27_channel_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)
        f.write("\n")

    print(f"status: {ALLOWED_STATUS}")
    print(f"validation_acc={val_acc:.4f} final_test_acc={te_acc:.4f}")
    print(f"per_snr_acc={per_snr}")
    print(f"int8_feasible={ok_int8} unsupported_ops={unsupported}")
    print(f"confusion_matrix ({len(CHANNEL_LABELS)}x{len(CHANNEL_LABELS)}):")
    print("        " + " ".join(f"{l[:4]:>4}" for l in CHANNEL_LABELS))
    for i, l in enumerate(CHANNEL_LABELS):
        print(f"{l:>8} " + " ".join(f"{cm[i, j]:4d}" for j in range(len(CHANNEL_LABELS))))
    print(f"report: {report_path}")

    # gate: the prototype must never assert a forbidden "done" status
    if ok_int8 is False:
        print("WARNING: unsupported ONNX ops present; int8 path blocked")
    sys.exit(0)


if __name__ == "__main__":
    main()
