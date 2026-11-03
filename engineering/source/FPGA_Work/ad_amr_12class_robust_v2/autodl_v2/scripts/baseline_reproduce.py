#!/usr/bin/env python3
"""Phase 1 baseline reproduction: train the V2 baseline (V1 architecture + V1
data, no augmentation / no curriculum / CE loss) and compare against V1.

This is the "reproduce V1" step.  The V2 baseline must match V1's published
metrics before any robustness axis is explored.  Runs a single trial with the
frozen baseline ``v2`` block (empty augmentation, no curriculum, CE loss).
"""

from __future__ import annotations

import argparse
import copy
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from training.utils import load_yaml
from v2.run import run_trial


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/v2_base.yaml")
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--output-root", default=None)
    args = parser.parse_args()

    base = load_yaml(args.config)
    cfg = copy.deepcopy(base)
    # Frozen baseline: V1 architecture + V1 channel, no V2 axes.
    cfg["v2"] = {
        "augmentation_groups": [],
        "snr_curriculum": "none",
        "class_sampling": "balanced",
        "loss": "cross_entropy",
        "optimizer": "adamw",
        "distillation": {"enabled": False},
    }
    epochs = args.epochs or int(cfg["training"]["epochs"])
    root = args.output_root or f"{base['output_root']}/baseline_reproduce"
    result = run_trial(cfg, "baseline", root, seed=args.seed, epochs=epochs)
    print(f"baseline reproduce: best_score={result['best_selection_score']:.4f} "
          f"best_epoch={result['best_epoch']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
