"""
qat_experiment.py
=================
Quantization-Aware Training (QAT) experiment for DSC-AMCNet.

This script documents a NEGATIVE RESULT (paper Section VIII-A): QAT
fine-tuning of DSC-AMCNet converges to only 48.2% overall accuracy versus
the 57% FP32 overall baseline, while plain static PTQ preserves FP32
accuracy within noise (+0.03 pp overall; +0.09 pp at +10 dB).
PTQ is therefore used exclusively for DSC-AMCNet.

Hypothesis (stated as such in the paper): SE Sigmoid activations may be
destabilized by fake-quantization perturbations inserted during QAT
[Jacob et al., 2017]. This appears specific to the SE-attention path:
for the SE-free LiteAMCNet baseline, QAT works as expected (56.60%
overall, +1.40 pp ABOVE FP32, recovering PTQ losses at 18 of 20 SNR
bins; peak recovery +4.75 pp at -6 dB).

Reporting convention: PTQ degradation = FP32 - INT8 (positive = accuracy
lost to quantization).
"""

import argparse
import sys
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn
import torch.quantization
from torch.utils.data import DataLoader, TensorDataset

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from models.dsc_amcnet import build_dsc_amcnet
from datasets.prepare_dataset import load_splits, load_by_snr


def main(args):
    device = torch.device("cpu")  # QAT must run on CPU for PyTorch static quant

    print("=" * 60)
    print("QAT Experiment — DSC-AMCNet (NEGATIVE RESULT)")
    print("=" * 60)
    print("\nWarning: QAT degraded accuracy in this architecture.")
    print("See docstring and paper Section V-C for analysis.\n")

    # Load data
    train_X, train_y, _, _, _, _ = load_splits(args.data, args.split)
    X_hi, y_hi, _                = load_by_snr(args.data, args.split, snr_min=10)

    train_loader = DataLoader(
        TensorDataset(torch.from_numpy(train_X).float(), torch.from_numpy(train_y).long()),
        batch_size=256, shuffle=True,
    )
    hi_loader = DataLoader(
        TensorDataset(torch.from_numpy(X_hi).float(), torch.from_numpy(y_hi).long()),
        batch_size=256,
    )

    # Build QAT model
    model = build_dsc_amcnet()
    model.load_state_dict(torch.load(args.checkpoint, map_location="cpu"))
    model.train()
    model.qconfig = torch.quantization.get_default_qconfig("fbgemm")
    torch.quantization.prepare_qat(model, inplace=True)

    optimizer = torch.optim.Adam(model.parameters(), lr=1e-4)
    criterion = nn.NLLLoss()

    print(f"Fine-tuning for {args.epochs} epochs with QAT ...\n")
    history = []
    for epoch in range(1, args.epochs + 1):
        model.train()
        for xb, yb in train_loader:
            optimizer.zero_grad()
            out = model(xb)
            loss = criterion(out, yb)
            loss.backward()
            optimizer.step()

        # Evaluate
        model.eval()
        correct, total = 0, 0
        with torch.no_grad():
            model_int8 = torch.quantization.convert(
                torch.quantization.prepare_qat(
                    build_dsc_amcnet().eval(), inplace=False
                ),
                inplace=False,
            )
            # Use the live QAT model (not fully converted) for per-epoch tracking
            for xb, yb in hi_loader:
                out = model(xb)
                correct += (out.argmax(1) == yb).sum().item()
                total += len(yb)
        acc = correct / total
        history.append(acc)
        print(f"  Epoch {epoch:3d}: High-SNR accuracy = {acc*100:.2f}%")

    print("\n" + "=" * 60)
    print("QAT RESULT SUMMARY")
    print("=" * 60)
    print(f"  Paper reference  : FP32 overall 57%; QAT converges to 48.2%")
    print(f"  Paper reference  : PTQ overall +0.03 pp; +0.09 pp at +10 dB")
    print(f"  QAT final epoch  : {history[-1]*100:.2f}% (this run)")
    print("\nConclusion: PTQ is the preferred quantization strategy for this "
          "architecture (paper Section VIII-A).")
    print("QAT is not recommended: SE Sigmoid activations may be destabilized "
          "by fake-quantization perturbations (stated as hypothesis).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--data",       required=True)
    parser.add_argument("--split",      required=True)
    parser.add_argument("--epochs", type=int, default=10)
    main(parser.parse_args())
