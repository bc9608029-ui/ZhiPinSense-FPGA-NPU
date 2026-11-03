"""
train.py
========
Training script for DSC-AMCNet on RML2016.10a (paper Section III-C protocol).

Protocol (paper Section III-C):
    Optimizer      : Adam, lr = 1e-3
    LR schedule    : ReduceLROnPlateau (patience = 5)
    Early stopping : patience = 15
    Batch size     : 512
    Max epochs     : 100
    Normalization  : per-window L2 norm (DSC-AMCNet only)
    Split          : locked 80/20 stratified train/test (split_indices.npz,
                     SEED = 42): train_idx (176,000), test_idx (44,000).
                     A 10% validation subset is carved from train_idx
                     (seed 42) to drive the scheduler and early stopping;
                     the locked test set is never used for model selection.

Expected result (paper Table II): 87.01% FP32 accuracy at +10 dB
(seed-to-seed variance +/- 0.23 pp across seeds 42/123/999; mean 85.69%).

Usage:
    python models/train.py \
        --data  datasets/RML2016.10a_dict.dat \
        --split datasets/split_indices.npz \
        --epochs 100 \
        --output models/checkpoints/dscamcnet_best.pt
"""

import argparse
import pickle
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset

sys.path.insert(0, str(Path(__file__).parent))
from dsc_amcnet import build_dsc_amcnet, normalize_window  # noqa: E402


class RML2016Dataset(Dataset):
    def __init__(self, X: np.ndarray, y: np.ndarray, l2_norm: bool = True):
        self.X = torch.from_numpy(X).float()
        self.y = torch.from_numpy(y).long()
        if l2_norm:
            self.X = normalize_window(self.X)

    def __len__(self):
        return len(self.y)

    def __getitem__(self, i):
        return self.X[i], self.y[i]


def load_rml2016(data_path: str):
    """Load RML2016.10a_dict.dat -> (X [N,2,128], y [N], snr [N])."""
    with open(data_path, "rb") as f:
        d = pickle.load(f, encoding="latin1")
    keys = sorted(d.keys(), key=lambda k: (k[0], k[1]))
    classes = sorted({k[0] for k in keys})
    cls_to_idx = {c: i for i, c in enumerate(classes)}
    X, y, snr = [], [], []
    for (mod, s) in keys:
        arr = d[(mod, s)]
        X.append(arr)
        y.extend([cls_to_idx[mod]] * len(arr))
        snr.extend([s] * len(arr))
    return (np.concatenate(X).astype(np.float32),
            np.asarray(y, dtype=np.int64),
            np.asarray(snr, dtype=np.int64))


def load_split(split_path: str):
    """Load the locked 80/20 split. Keys: train_idx (176,000),
    test_idx (44,000)."""
    z = np.load(split_path)
    return z["train_idx"], z["test_idx"]


def make_val_subset(train_idx: np.ndarray, frac: float = 0.10,
                    seed: int = 42):
    """Carve a validation subset from the training indices (never from the
    locked test set)."""
    rng = np.random.default_rng(seed)
    perm = rng.permutation(len(train_idx))
    n_val = int(len(train_idx) * frac)
    return train_idx[perm[n_val:]], train_idx[perm[:n_val]]


@torch.no_grad()
def evaluate(model, loader, device):
    model.eval()
    correct = total = 0
    for xb, yb in loader:
        xb, yb = xb.to(device), yb.to(device)
        pred = model(xb).argmax(dim=1)
        correct += (pred == yb).sum().item()
        total += yb.numel()
    return correct / max(total, 1)


def main(args):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    X, y, snr = load_rml2016(args.data)
    train_idx, test_idx = load_split(args.split)
    tr_idx, val_idx = make_val_subset(train_idx, seed=args.seed)

    train_loader = DataLoader(RML2016Dataset(X[tr_idx], y[tr_idx]),
                              batch_size=args.batch_size, shuffle=True,
                              num_workers=2)
    val_loader = DataLoader(RML2016Dataset(X[val_idx], y[val_idx]),
                            batch_size=args.batch_size, shuffle=False,
                            num_workers=2)
    hi = test_idx[snr[test_idx] == 10]  # +10 dB bin (paper convention)
    hi_loader = DataLoader(RML2016Dataset(X[hi], y[hi]),
                           batch_size=args.batch_size, shuffle=False)

    model = build_dsc_amcnet().to(device)
    n_par = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"DSC-AMCNet parameters: {n_par:,} (paper: 4,961)")

    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="max", patience=5)

    best_val, stale = 0.0, 0
    for epoch in range(1, args.epochs + 1):
        model.train()
        for xb, yb in train_loader:
            xb, yb = xb.to(device), yb.to(device)
            optimizer.zero_grad()
            loss = criterion(model(xb), yb)
            loss.backward()
            optimizer.step()
        val_acc = evaluate(model, val_loader, device)
        scheduler.step(val_acc)
        if val_acc > best_val:
            best_val, stale = val_acc, 0
            torch.save(model.state_dict(), args.output)
        else:
            stale += 1
        print(f"Epoch {epoch:3d}/{args.epochs}  val={val_acc:.4f}  "
              f"best={best_val:.4f}")
        if stale >= 15:
            print("Early stopping (patience = 15).")
            break

    model.load_state_dict(torch.load(args.output, map_location=device))
    hi_acc = evaluate(model, hi_loader, device)
    print(f"\n+10 dB test accuracy (locked split): {hi_acc*100:.2f}% "
          f"(paper FP32: 87.01%, seed variance +/-0.23 pp)")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Train DSC-AMCNet (paper protocol)")
    p.add_argument("--data", required=True)
    p.add_argument("--split", required=True)
    p.add_argument("--epochs", type=int, default=100)
    p.add_argument("--batch_size", type=int, default=512)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--output", default="models/checkpoints/dscamcnet_best.pt")
    main(p.parse_args())
