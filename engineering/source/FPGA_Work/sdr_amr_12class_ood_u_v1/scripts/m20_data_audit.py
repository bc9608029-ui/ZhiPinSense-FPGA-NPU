"""M20 data audit (Section 二 / 五 / 六).

Fail-closed verification of the model identity (checkpoint / ONNX / NPU JSON /
NPU raw SHA) and of the OOD-U data isolation contract: the three splits
(oe_aux_train / ood_validation / ood_final_test) are generated for the known
12-class (ID) domain and every unknown family (near_12 / far / ambiguous), their
split SHAs are computed, zero-overlap is asserted across all of them, and the
generator-shortcut audit runs on ``ood_validation``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from ood_u import contract
from ood_u.data import (
    SplitRecords,
    assert_no_overlap,
    generate_id_split,
    generate_ood_split,
    signal_config,
    split_sha,
)
from ood_u.model import sha256_file
from ood_u.shortcut import audit_shortcut, assert_shared_domain
from scripts.m20_common import (
    PROJECT_ROOT,
    add_common_args,
    emit_result,
    new_run_id,
    read_json,
    resolve_path,
    run,
    write_json,
)

_NEAR_FAMILY = "near_12"


def _check_artifact_sha(path: str | Path, expected: str, label: str) -> str:
    actual = sha256_file(path)
    if actual != expected:
        raise RuntimeError(f"{label} SHA-256 mismatch: expected {expected}, got {actual}")
    return actual


def _audit(records_by_split: dict[str, dict[str, SplitRecords]]) -> dict[str, Any]:
    # Aggregate every record for zero-overlap and shared-domain checks.
    all_records: list[SplitRecords] = []
    for split, families in records_by_split.items():
        all_records.extend(families.values())
    assert_no_overlap(*all_records)
    assert_shared_domain(*all_records)

    split_report: dict[str, dict[str, Any]] = {}
    for split, families in records_by_split.items():
        split_report[split] = {}
        for family, rec in families.items():
            split_report[split][family] = {
                "samples": len(rec),
                "split_sha256": split_sha(rec),
            }

    # Generator-shortcut audit on ood_validation: ID vs (near_12 + far).
    val = records_by_split["ood_validation"]
    id_planar = val["id"].planar
    ood_planar = np.concatenate([val[_NEAR_FAMILY].planar, val["far"].planar], axis=0)
    feature_auroc, shortcut_detected = audit_shortcut(id_planar, ood_planar)
    if shortcut_detected:
        raise RuntimeError(
            "generator shortcut detected: a single cheap feature separates ID from OOD "
            f"with |AUROC-0.5| >= 0.40: {feature_auroc}"
        )

    return {
        "shared_signal_domain": signal_config(),
        "splits": split_report,
        "generator_shortcut": {
            "feature_auroc": feature_auroc,
            "shortcut_detected": shortcut_detected,
        },
    }


def main(args: argparse.Namespace) -> None:
    run_id = new_run_id()
    out_dir = resolve_path(args.out_dir or "runs/m20_data_audit")
    checkpoint = resolve_path(args.checkpoint)

    identity = {
        "checkpoint_sha256": _check_artifact_sha(checkpoint, contract.CHECKPOINT_SHA256, "checkpoint"),
        "onnx_sha256": _check_artifact_sha(
            resolve_path("model_12class/ad_amr_v1_1_opset17.onnx"), contract.ONNX_SHA256, "ONNX"),
        "npu_json_sha256": _check_artifact_sha(
            resolve_path("model_12class/model_12class.json"), contract.NPU_JSON_SHA256, "NPU JSON"),
        "npu_raw_sha256": _check_artifact_sha(
            resolve_path("model_12class/model_12class.raw"), contract.MODEL_SHA256, "NPU raw weights"),
    }

    count_per_class = int(args.count_per_class)
    count_per_modulation = int(args.count_per_modulation)
    snr = tuple(contract.BENCHMARK_SNR_VALUES)

    records_by_split: dict[str, dict[str, SplitRecords]] = {}
    for split in ("oe_aux_train", "ood_validation", "ood_final_test"):
        records_by_split[split] = {
            "id": generate_id_split(split, seed=contract.OOD_SEED, count_per_class=count_per_class, snr_values=snr),
            _NEAR_FAMILY: generate_ood_split(_NEAR_FAMILY, split, seed=contract.OOD_SEED,
                                             count_per_modulation=count_per_modulation, snr_values=snr),
            "far": generate_ood_split("far", split, seed=contract.OOD_SEED,
                                      count_per_modulation=count_per_modulation, snr_values=snr),
            "ambiguous": generate_ood_split("ambiguous", split, seed=contract.OOD_SEED,
                                            count_per_modulation=count_per_modulation, snr_values=snr),
        }

    audit = _audit(records_by_split)

    report: dict[str, Any] = {
        "run_id": run_id,
        "step": "data_audit",
        "model_identity": identity,
        "label_order": list(contract.LABEL_ORDER_12),
        "input_contract": {"shape": list(contract.INPUT_SHAPE)},
        "output_contract": {
            "dim": contract.OUTPUT_DIM,
            "numeric_type": contract.OUTPUT_NUMERIC_TYPE,
            "kind": contract.OUTPUT_KIND,
        },
        "count_per_class": count_per_class,
        "count_per_modulation": count_per_modulation,
        "snr_values": list(snr),
        "ood_seed": contract.OOD_SEED,
        "near_family": _NEAR_FAMILY,
        "audit": audit,
    }
    out_path = write_json(out_dir / "data_audit_report.json", report)
    emit_result("PASS", run_id,
                model_sha256=identity["npu_raw_sha256"][:16] + "...",
                shortcut_detected=audit["generator_shortcut"]["shortcut_detected"],
                report=str(out_path.relative_to(PROJECT_ROOT)))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="M20 data audit")
    add_common_args(parser)
    parser.add_argument("--count-per-class", type=int, default=8)
    parser.add_argument("--count-per-modulation", type=int, default=8)
    return parser


if __name__ == "__main__":
    run(build_parser(), main)
