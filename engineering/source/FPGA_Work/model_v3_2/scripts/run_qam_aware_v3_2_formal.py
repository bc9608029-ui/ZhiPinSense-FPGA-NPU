"""Run the three-seed V3.2 formal trajectory with strict per-seed resume.

Each seed trains, evaluates and exports into its own directory
(``<formal_root>/seeds/seed<seed>``), so no seed can overwrite another seed's
checkpoint, log or table.  The training configuration (distillation +
class weights) is read from the frozen ``selected_candidate.yaml`` and is never
re-derived here, so a resumed job cannot silently change the selected
hyperparameters.

Resume semantics (safe to re-run after an interruption):

* a seed whose ``SEED_DONE`` marker exists is skipped entirely;
* a seed with a ``last.pt`` but no marker resumes from that exact checkpoint;
* a seed with neither starts a clean trajectory.

After every seed is finished, the multi-seed acceptance gate is applied.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

from evaluation.check_qam_aware_v3_2_multi_seed_acceptance import run_multi_seed_acceptance
from evaluation.evaluate_qam_aware_v3_2 import evaluate_v3_2
from scripts.export_qam_aware_v3_2_onnx import export_v3_2
from training.train_qam_aware_v3_2 import train_v3_2
from training.qam_aware_v3_2_utils import write_text_lf
from training.utils import PROJECT_ROOT, resolve_project_path

DONE_MARKER = "SEED_DONE.json"


def _default_seeds(gate_path: str) -> list[int]:
    raw = yaml.safe_load(resolve_project_path(gate_path).read_text(encoding="utf-8"))
    return [int(seed) for seed in raw["multi_seed"]["seeds"]]


def _write_seed_config(
    base_config_path: str,
    seed: int,
    seed_dir: Path,
    training: dict,
) -> Path:
    override = {
        "experiment_config": base_config_path,
        "seed": seed,
        "output_root": seed_dir.relative_to(PROJECT_ROOT).as_posix(),
        "training": {
            "distillation": dict(training["distillation"]),
            "class_weights": dict(training["class_weights"]),
        },
    }
    config_path = seed_dir / "config" / "seed_config.yaml"
    write_text_lf(config_path, yaml.safe_dump(override, sort_keys=False))
    return config_path


def _run_seed(base_config_path: str, seed: int, seed_dir: Path, training: dict) -> dict:
    done_marker = seed_dir / DONE_MARKER
    if done_marker.is_file():
        return {"seed": seed, "status": "skipped", "reason": "SEED_DONE marker present"}

    config_path = _write_seed_config(base_config_path, seed, seed_dir, training)
    last_pt = seed_dir / "checkpoints" / "last.pt"
    resume = str(last_pt) if last_pt.is_file() else None
    train_v3_2(str(config_path), resume=resume)
    evaluate_v3_2(str(config_path))
    export_v3_2(str(config_path))

    manifest_path = seed_dir / "logs" / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    write_text_lf(
        done_marker,
        json.dumps(
            {
                "seed": seed,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "best_epoch": int(manifest["best_epoch"]),
                "status": "completed",
            },
            indent=2,
        )
        + "\n",
    )
    return {"seed": seed, "status": "completed" if not resume else "resumed", "best_epoch": int(manifest["best_epoch"])}


def run_formal_seeds(
    base_config_path: str,
    selected_candidate_path: str,
    seeds: list[int],
    formal_root: str = "outputs/qam_aware_v3_2/formal",
    gate_path: str = "configs/qam_aware_v3_2_acceptance.yaml",
) -> dict:
    candidate_file = resolve_project_path(selected_candidate_path)
    candidate = yaml.safe_load(candidate_file.read_text(encoding="utf-8"))
    training = candidate["training"]
    candidate_sha = hashlib.sha256(candidate_file.read_bytes()).hexdigest()

    root = resolve_project_path(formal_root)
    seed_dirs = [root / "seeds" / f"seed{seed}" for seed in seeds]
    outcomes = [_run_seed(base_config_path, seed, seed_dir, training) for seed, seed_dir in zip(seeds, seed_dirs)]

    aggregate_out = root / "aggregate" / "v3_2_acceptance.json"
    gate = run_multi_seed_acceptance(seed_dirs, gate_path, str(aggregate_out))

    return {
        "selected_variant": candidate.get("selected_variant"),
        "selected_candidate_sha256": candidate_sha,
        "seeds": seeds,
        "outcomes": outcomes,
        "gate_passed": bool(gate["passed"]),
        "gate_report": str(aggregate_out),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/qam_aware_v3_2.yaml")
    parser.add_argument(
        "--selected",
        default="outputs/qam_aware_v3_2/formal/selected_candidate.yaml",
    )
    parser.add_argument("--seeds", nargs="*", type=int, default=None)
    parser.add_argument("--formal-root", default="outputs/qam_aware_v3_2/formal")
    parser.add_argument("--gates", default="configs/qam_aware_v3_2_acceptance.yaml")
    args = parser.parse_args()

    seeds = args.seeds if args.seeds else _default_seeds(args.gates)
    result = run_formal_seeds(args.config, args.selected, seeds, args.formal_root, args.gates)
    print(json.dumps(result, indent=2))
    if not result["gate_passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
