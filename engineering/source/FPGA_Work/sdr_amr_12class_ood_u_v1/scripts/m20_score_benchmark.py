"""M20 score benchmark (Section 七).

Generate the ``ood_validation`` ID / near_12 / far / ambiguous / impaired-ID
records and benchmark all five OOD-U score methods (MSP / Entropy / MaxLogit /
LogitMargin / Energy).  The impaired-ID accept rate at the 99% accept point is
reported so method selection can enforce the OOD-R (known-class) protection.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ood_u import contract
from ood_u.benchmark import run_score_benchmark
from ood_u.data import generate_id_split, generate_ood_split
from ood_u.model import load_model
from ood_u.protection import generate_protection_records
from scripts.m20_common import (
    PROJECT_ROOT,
    add_common_args,
    emit_result,
    new_run_id,
    resolve_path,
    run,
    write_json,
)

_NEAR_FAMILY = "near_12"


def main(args: argparse.Namespace) -> None:
    run_id = new_run_id()
    out_dir = resolve_path(args.out_dir or "runs/m20_score_benchmark")
    model = load_model(resolve_path(args.checkpoint))

    count_per_class = int(args.count_per_class)
    count_per_modulation = int(args.count_per_modulation)
    snr = tuple(contract.BENCHMARK_SNR_VALUES)

    id_val = generate_id_split("ood_validation", seed=contract.OOD_SEED,
                               count_per_class=count_per_class, snr_values=snr)
    near_val = generate_ood_split(_NEAR_FAMILY, "ood_validation", seed=contract.OOD_SEED,
                                  count_per_modulation=count_per_modulation, snr_values=snr)
    far_val = generate_ood_split("far", "ood_validation", seed=contract.OOD_SEED,
                                 count_per_modulation=count_per_modulation, snr_values=snr)
    amb_val = generate_ood_split("ambiguous", "ood_validation", seed=contract.OOD_SEED,
                                 count_per_modulation=count_per_modulation, snr_values=snr)
    impaired_id_val = generate_protection_records(
        "clean", "ood_validation", seed=contract.OOD_SEED, count_per_class=count_per_class)

    report = run_score_benchmark(
        model, id_val, near_val, far_val, amb_val, impaired_id_val, temperature=1.0)
    report["run_id"] = run_id
    report["step"] = "score_benchmark"
    report["near_family"] = _NEAR_FAMILY
    report["snr_values"] = list(snr)

    out_path = write_json(out_dir / "benchmark_report.json", report)
    methods = report["methods"]
    chosen = max(methods, key=lambda m: methods[m]["overall"]["auroc"])
    emit_result("PASS", run_id,
                best_overall_auroc=round(methods[chosen]["overall"]["auroc"], 4),
                best_method=chosen,
                report=str(out_path.relative_to(PROJECT_ROOT)))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="M20 score benchmark")
    add_common_args(parser)
    parser.add_argument("--count-per-class", type=int, default=20)
    parser.add_argument("--count-per-modulation", type=int, default=20)
    return parser


if __name__ == "__main__":
    run(build_parser(), main)
