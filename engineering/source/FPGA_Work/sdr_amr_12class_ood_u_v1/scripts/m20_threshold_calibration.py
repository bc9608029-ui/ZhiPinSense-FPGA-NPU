"""M20 threshold calibration + manifest freeze (Section 八).

Select the OOD-U score method by rank aggregation over the ``ood_validation``
benchmark, scan Energy temperature (when Energy wins), compute the three frozen
working points, and write the write-once OOD-U threshold manifest.  The final
test split is never touched here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from ood_u import contract
from ood_u.benchmark import run_score_benchmark
from ood_u.calibrate import calibrate, select_method
from ood_u.data import generate_id_split, generate_ood_split, split_sha
from ood_u.manifest import build_ood_u_manifest, manifest_sha256, write_ood_u_manifest
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


def _calibration_hashes(id_val: Any, near_val: Any, far_val: Any) -> tuple[str, str]:
    split_shas = sorted([split_sha(id_val), split_sha(near_val), split_sha(far_val)])
    split_hash = hashlib.sha256("\n".join(split_shas).encode("utf-8")).hexdigest()
    sample_shas = sorted(id_val.sample_hashes + near_val.sample_hashes + far_val.sample_hashes)
    dataset_hash = hashlib.sha256("\n".join(sample_shas).encode("utf-8")).hexdigest()
    return dataset_hash, split_hash


def main(args: argparse.Namespace) -> None:
    run_id = new_run_id()
    out_dir = resolve_path(args.out_dir or "runs/m20_threshold_calibration")
    manifest_path = resolve_path(args.manifest or "runs/m20_threshold_calibration/ood_u_threshold_manifest.json")
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

    benchmark = run_score_benchmark(
        model, id_val, near_val, far_val, amb_val, impaired_id_val, temperature=1.0)

    chosen_method, ranks = select_method(benchmark)
    result = calibrate(model, id_val, near_val, far_val, chosen_method=chosen_method)

    dataset_hash, split_hash = _calibration_hashes(id_val, near_val, far_val)
    manifest = build_ood_u_manifest(
        score_method=result["score_method"],
        temperature=result["temperature"],
        threshold=result["threshold"],
        working_points=result["working_points"],
        target_operating_point=result["target_operating_point"],
        calibration_dataset_sha256=dataset_hash,
        calibration_split_sha256=split_hash,
        sample_count={"id": len(id_val), "ood": len(near_val) + len(far_val)},
        creation_seed=contract.OOD_SEED,
    )
    write_ood_u_manifest(manifest, manifest_path)

    report: dict[str, Any] = {
        "run_id": run_id,
        "step": "threshold_calibration",
        "score_method": result["score_method"],
        "temperature": result["temperature"],
        "threshold": result["threshold"],
        "target_operating_point": result["target_operating_point"],
        "working_points": result["working_points"],
        "method_ranks": ranks,
        "calibration_dataset_sha256": dataset_hash,
        "calibration_split_sha256": split_hash,
        "manifest_sha256": manifest_sha256(manifest),
        "manifest_path": str(manifest_path.relative_to(PROJECT_ROOT)),
        "benchmark_summary": {
            m: {
                "overall_auroc": benchmark["methods"][m]["overall"]["auroc"],
                "fpr95": benchmark["methods"][m]["overall"]["fpr95"],
                "impaired_id_accept_at_99pct": benchmark["methods"][m]["impaired_id_accept_at_99pct"],
            }
            for m in benchmark["methods"]
        },
    }
    out_path = write_json(out_dir / "calibration_report.json", report)
    emit_result("PASS", run_id,
                score_method=result["score_method"],
                temperature=result["temperature"],
                threshold=round(result["threshold"], 6),
                manifest_sha256=report["manifest_sha256"][:16] + "...",
                report=str(out_path.relative_to(PROJECT_ROOT)))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="M20 threshold calibration + manifest freeze")
    add_common_args(parser)
    parser.add_argument("--manifest", default=None,
                        help="path to write the OOD-U threshold manifest")
    parser.add_argument("--count-per-class", type=int, default=20)
    parser.add_argument("--count-per-modulation", type=int, default=20)
    return parser


if __name__ == "__main__":
    run(build_parser(), main)
