"""Freeze the OOD threshold manifest from the OOD baselines report.

The OOD baselines step (``run_ood_baselines.sh``) already locks the three working
points on ``ood_validation`` and calibrates the Energy temperature.  This runner
promotes those locked values into a write-once ``ood_threshold_manifest.json`` so
the decision boundary is persisted and versioned rather than silently re-fitted.

SHA semantics (documented, deterministic):
  * ``model_sha256``                = SHA-256 of the frozen 24-class label order
                                      (``label_contract_sha256()`` — the model's
                                      output-class identity).
  * ``checkpoint_sha256``           = from ``final_checkpoint_manifest.json``.
  * ``calibration_dataset_sha256``  = the RadioML HDF5 ``dataset_sha256``.
  * ``calibration_split_sha256``    = SHA-256 of the canonical calibration-split
                                      definition (family + ``ood_validation`` +
                                      seed + count_per_modulation); reproducible
                                      because OOD samples are generated
                                      deterministically from that triple.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from datasets.ood_dataset import OOD_FAMILIES
from ood.threshold_manifest import build_threshold_manifest, write_threshold_manifest
from training.utils import load_yaml, resolve_project_path
from v2.candidate_signature import label_contract_sha256


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def calibration_split_sha256(threshold_family: str, ood_seed: int,
                             count_per_modulation: int) -> str:
    return _sha256_text(_canonical({
        "family": threshold_family,
        "split": "ood_validation",
        "seed": int(ood_seed),
        "count_per_modulation": int(count_per_modulation),
    }))


def _rml24_node(report: dict[str, Any]) -> dict[str, Any]:
    return report.get("rml24") if isinstance(report.get("rml24"), dict) else report


def freeze_thresholds(final_manifest_path: str | Path, ood_report_path: str | Path,
                      *, output: str | Path | None = None, score_method: str = "energy",
                      target_operating_point: str = "balanced",
                      ood_seed: int | None = None, count_per_modulation: int = 256) -> dict[str, Any]:
    final = json.loads(Path(final_manifest_path).read_text(encoding="utf-8"))
    report = json.loads(Path(ood_report_path).read_text(encoding="utf-8"))
    node = _rml24_node(report)

    method_node = node["families"][score_method]
    thresholds = method_node["thresholds"]
    temperature = float(node["calibrated_temperature"])
    id_samples = int(node["id_samples"])
    threshold_family = str(node["threshold_family"])
    seed = int(ood_seed) if ood_seed is not None else 2026
    ood_calib_samples = len(OOD_FAMILIES[threshold_family]) * int(count_per_modulation)

    manifest = build_threshold_manifest(
        model_sha256=label_contract_sha256(),
        checkpoint_sha256=str(final["checkpoint_sha256"]),
        score_method=score_method,
        thresholds=thresholds,
        calibration_dataset_sha256=str(final["dataset_sha256"]),
        calibration_split_sha256=calibration_split_sha256(
            threshold_family, seed, count_per_modulation),
        target_operating_point=target_operating_point,
        calibration_samples={"id": id_samples, "ood": ood_calib_samples},
        creation_seed=seed,
        temperature=temperature,
    )
    destination = Path(output or "runs/ood_baselines/ood_threshold_manifest.json")
    write_threshold_manifest(manifest, destination)
    return {"manifest": str(destination), **manifest}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="runs/rml24_base/formal/final_checkpoint_manifest.json")
    parser.add_argument("--ood-report", default="runs/ood_baselines/ood_baselines.json")
    parser.add_argument("--config", default="configs/rml24_base.yaml")
    parser.add_argument("--output", default=None)
    parser.add_argument("--score-method", default="energy")
    parser.add_argument("--target-operating-point", default="balanced")
    parser.add_argument("--ood-seed", type=int, default=None)
    parser.add_argument("--count-per-modulation", type=int, default=256)
    args = parser.parse_args()

    seed = args.ood_seed
    if seed is None:
        seed = int(load_yaml(resolve_project_path(args.config))["seed"])

    result = freeze_thresholds(
        args.manifest, args.ood_report, output=args.output,
        score_method=args.score_method, target_operating_point=args.target_operating_point,
        ood_seed=seed, count_per_modulation=args.count_per_modulation,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("RML24_THRESHOLD_FREEZE_OK")


if __name__ == "__main__":
    main()
