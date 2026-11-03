#!/usr/bin/env python3
"""evaluate_fix10class24_rf_adapt.py -- F1-F4 evaluation for the pilot adaptation.

Preregistered evaluation protocol (frozen):

* F1  clean-hold regression:  24 clean24_smoke tensors; must stay >= 24/24 baseline.
* F2  single-SDR frozen control: 23/24 reference; OQPSK(11500)->32PSK is the known
     failure to check for a fix (the OQPSK fix check).
* F3  dual-SDR post-freeze open test: 18/24 forced reference (20/24 classes); open
     test, never used for model selection.
* F4  3-seed statistics: min/mean/max/std over seeds {17,29,43}.

The tensor->label wiring for F1/F2/F3 is data-dependent (external dirs) and runs in
the training environment (torch).  F4 is pure-stdlib and runnable here via
``--f4-stats``.  This script never writes RF_PASS / PROJECT_COMPLETE / FINAL_*.

Usage::

    # F4 seed statistics from already-trained run results (pure stdlib):
    python scripts/evaluate_fix10class24_rf_adapt.py --f4-stats --runs-dir runs/pilot

    # Full F1-F3 (torch):
    python scripts/evaluate_fix10class24_rf_adapt.py \
        --checkpoint runs/pilot/best.pt --model-def <module> \
        --f1-clean24 clean24_smoke --output results/rf_adapt_prep1/evaluation.json
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, os.pardir, "contracts"))
import rml24_dualsdr_rf_dataset_v1 as C  # noqa: E402

SEEDS = C.PILOT_TRAINING_SPEC["seeds"]


def compute_seed_statistics(run_results):
    """Pure-stdlib F4: aggregate a list of per-run result dicts into seed stats.

    ``run_results`` is a list of dicts each carrying ``seed`` and one or more
    numeric metric fields (e.g. ``best_val_accuracy``, ``test_accuracy``).  Returns
    a dict mapping metric -> {min, mean, max, std} across seeds, keyed by metric.
    """
    by_seed = {}
    for r in run_results:
        by_seed[r["seed"]] = r

    metrics = {}
    for seed, r in sorted(by_seed.items()):
        for k, v in r.items():
            if isinstance(v, (int, float)) and k not in ("seed",):
                metrics.setdefault(k, []).append((seed, v))

    out = {}
    for metric, pairs in metrics.items():
        vals = [v for _, v in pairs]
        out[metric] = {
            "min": min(vals), "mean": statistics.mean(vals),
            "max": max(vals),
            "std": statistics.pstdev(vals) if len(vals) > 1 else 0.0,
            "by_seed": {str(s): v for s, v in pairs},
        }
    return out


def _load_run_results(runs_dir):
    runs_dir = Path(runs_dir)
    if not runs_dir.is_dir():
        raise SystemExit(f"runs dir not found: {runs_dir}")
    results = []
    for p in sorted(runs_dir.glob("run_*.json")):
        results.append(json.loads(p.read_text(encoding="utf-8")))
    if not results:
        raise SystemExit(f"no run_*.json under {runs_dir}")
    seeds_seen = sorted({r.get("seed") for r in results})
    if set(seeds_seen) != set(SEEDS):
        raise SystemExit(
            f"seed coverage {seeds_seen} != preregistered {list(SEEDS)}")
    return results


def _f4_stats(runs_dir):
    results = _load_run_results(runs_dir)
    stats = compute_seed_statistics(results)
    print(json.dumps(stats, indent=2, sort_keys=True))
    return 0


def require_torch():
    try:
        import torch  # noqa: F401
        return torch
    except ImportError:
        raise SystemExit(
            "torch not available; F1/F2/F3 require the training env. "
            "F4 (--f4-stats) is pure stdlib and runs here.")


def run_full(args):
    torch = require_torch()
    import numpy as np
    # Model + tensor loading is data-dependent and delegated to the training
    # environment.  This scaffold documents the F1/F2/F3 contract and refuses to
    # half-run on missing external dirs.
    missing = []
    for name, path in (("f1_clean24", args.f1_clean24),
                       ("f2_single_sdr", args.f2_single_sdr),
                       ("f3_dual_sdr", args.f3_dual_sdr)):
        if not path or not os.path.isdir(path):
            missing.append((name, path))
    if missing:
        raise SystemExit(
            "external eval dirs not present in this environment: "
            + ", ".join(f"{n}={p or '<unset>'}" for n, p in missing)
            + " -- F1/F2/F3 run in the training env with the archived captures")
    raise SystemExit(
        "full F1/F2/F3 tensor evaluation is wired in the training repo; this "
        "prep scaffold verifies the protocol and the F4 statistics only.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--f4-stats", action="store_true")
    ap.add_argument("--runs-dir", default="runs/pilot")
    ap.add_argument("--checkpoint", default=None)
    ap.add_argument("--model-def", default=None)
    ap.add_argument("--f1-clean24", default=None)
    ap.add_argument("--f2-single-sdr", default=None)
    ap.add_argument("--f3-dual-sdr", default=None)
    ap.add_argument("--output", default="results/rf_adapt_prep1/evaluation.json")
    args = ap.parse_args()

    if args.f4_stats:
        return _f4_stats(args.runs_dir)
    return run_full(args)


if __name__ == "__main__":
    sys.exit(main())
