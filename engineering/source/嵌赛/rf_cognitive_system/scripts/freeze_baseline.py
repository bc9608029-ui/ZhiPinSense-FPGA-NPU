"""Create or verify the Baseline V1 fairness lock using SHA-256 hashes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from training.utils import PROJECT_ROOT


LOCKED_FILES = (
    "configs/baseline.yaml",
    "datasets/modulation_generator.py",
    "datasets/synthetic_dataset.py",
    "channel/awgn.py",
    "channel/fading.py",
    "channel/impairments.py",
    "channel/channel_pipeline.py",
    "models/baseline_cnn.py",
    "training/trainer.py",
    "training/metrics.py",
    "training/utils.py",
    "train.py",
    "evaluation/evaluate.py",
    "evaluation/snr_sweep.py",
    "evaluation/confusion_matrix.py",
    "evaluation/dataset_audit.py",
    "evaluation/baseline_report.py",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current_hashes() -> dict[str, str]:
    return {name: digest(PROJECT_ROOT / name) for name in LOCKED_FILES}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    lock_path = PROJECT_ROOT / "configs" / "baseline_v1_lock.json"
    if args.verify:
        recorded = json.loads(lock_path.read_text(encoding="utf-8"))["sha256"]
        changed = {name: {"expected": recorded.get(name), "actual": value} for name, value in current_hashes().items() if recorded.get(name) != value}
        if changed:
            raise SystemExit("Baseline V1 lock mismatch:\n" + json.dumps(changed, indent=2))
        print(f"Verified {len(recorded)} locked Baseline V1 files.")
        return
    manifest = {
        "name": "Baseline V1 fairness lock",
        "policy": "Future comparisons must reuse the locked dataset distribution, ChannelPipeline, split generation, and evaluation sets. Any intentional change requires a new versioned baseline.",
        "sha256": current_hashes(),
    }
    lock_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote {lock_path} with {len(LOCKED_FILES)} hashes.")


if __name__ == "__main__":
    main()
