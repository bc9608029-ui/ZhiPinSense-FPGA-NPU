"""M20 final blind test (Section 十).

Run the frozen-threshold blind test exactly once on ``ood_final_test`` using the
read-only OOD-U manifest (method / temperature / threshold).  Reports the full
metric set and then marks the single-access audit flag.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ood_u import contract
from ood_u.blind_test import run_blind_test
from ood_u.data import generate_id_split, generate_ood_split
from ood_u.model import load_model
from ood_u.manifest import read_ood_u_manifest
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
    out_dir = resolve_path(args.out_dir or "runs/m20_final_blind_test")
    manifest_path = resolve_path(args.manifest or "runs/m20_threshold_calibration/ood_u_threshold_manifest.json")
    manifest = read_ood_u_manifest(manifest_path)
    model = load_model(resolve_path(args.checkpoint))

    count_per_class = int(args.count_per_class)
    count_per_modulation = int(args.count_per_modulation)
    snr = tuple(contract.BENCHMARK_SNR_VALUES)

    id_test = generate_id_split("ood_final_test", seed=contract.OOD_SEED,
                                count_per_class=count_per_class, snr_values=snr)
    near_test = generate_ood_split(_NEAR_FAMILY, "ood_final_test", seed=contract.OOD_SEED,
                                   count_per_modulation=count_per_modulation, snr_values=snr)
    far_test = generate_ood_split("far", "ood_final_test", seed=contract.OOD_SEED,
                                  count_per_modulation=count_per_modulation, snr_values=snr)
    amb_test = generate_ood_split("ambiguous", "ood_final_test", seed=contract.OOD_SEED,
                                  count_per_modulation=count_per_modulation, snr_values=snr)

    report = run_blind_test(
        model, manifest_path,
        id_test=id_test, near_test=near_test, far_test=far_test, amb_test=amb_test,
        audit_dir=out_dir, run_id=run_id, n_boot=int(args.n_boot),
    )
    report["step"] = "final_blind_test"

    out_path = write_json(out_dir / "blind_test_report.json", report)
    emit_result("PASS", run_id,
                score_method=report["score_method"],
                threshold=round(report["threshold"], 6),
                id_accept_rate=round(report["id_accept_rate"], 4),
                near_reject_rate=round(report["near_reject_rate"], 4),
                far_reject_rate=round(report["far_reject_rate"], 4),
                ood_detection_accuracy=round(report["ood_detection_accuracy"], 4),
                report=str(out_path.relative_to(PROJECT_ROOT)))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="M20 final blind test (single access)")
    add_common_args(parser)
    parser.add_argument("--manifest", default=None,
                        help="path to the frozen OOD-U threshold manifest")
    parser.add_argument("--count-per-class", type=int, default=20)
    parser.add_argument("--count-per-modulation", type=int, default=20)
    parser.add_argument("--n-boot", type=int, default=1000)
    return parser


if __name__ == "__main__":
    run(build_parser(), main)
