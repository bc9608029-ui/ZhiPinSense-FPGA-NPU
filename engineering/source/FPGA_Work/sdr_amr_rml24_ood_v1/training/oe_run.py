"""Outlier Exposure + Energy training entrypoint for the 24-class model.

Trains the ``RML2018_24_ROBUST_CANDIDATE`` with the OE+Energy loss (see
``training.oe_trainer.OETrainer``) using the same loader/eval plumbing as the
closed-set baseline.  Semantic OOD baselines are reported separately by
``run_ood_baselines.sh`` (they compare the benchmark and OE models side by side).
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from training.oe_trainer import OETrainer
from training.rml24_run import run_rml24_trial
from training.utils import load_yaml


def run_oe_trial(config: dict[str, Any] | str, trial_name: str,
                 output_root: str | Path, seed: int | None = None,
                 epochs: int | None = None, *, ood_domains: list[str] | None = None,
                 eval_samples: int | None = None, quant_samples: int | None = None,
                 channel_ood_samples: int | None = None) -> dict[str, Any]:
    cfg = copy.deepcopy(config) if isinstance(config, dict) else load_yaml(config)
    seed = int(seed if seed is not None else cfg["seed"])
    epochs = int(epochs if epochs is not None else cfg["training"]["epochs"])
    return run_rml24_trial(
        cfg, trial_name, output_root, seed, epochs, trainer_cls=OETrainer,
        eval_baseline=True, eval_fake_int8=True, eval_channel_ood=True,
        ood_domains=ood_domains, eval_samples=eval_samples,
        quant_samples=quant_samples, channel_ood_samples=channel_ood_samples,
    )


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/oe_energy.yaml")
    parser.add_argument("--trial", default="seed3407")
    parser.add_argument("--output-root", default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--epochs", type=int, default=None)
    args = parser.parse_args()
    cfg = load_yaml(args.config)
    result = run_oe_trial(cfg, args.trial, args.output_root or cfg["output_root"],
                          args.seed, args.epochs)
    print(f"oe_energy done: trial={result['trial']} "
          f"best_selection_score={result['best_selection_score']:.4f}")


if __name__ == "__main__":
    main()
