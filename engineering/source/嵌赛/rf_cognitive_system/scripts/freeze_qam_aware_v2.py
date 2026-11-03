"""Create or verify the QAM-Aware V2 source/config SHA-256 manifest."""

from __future__ import annotations

import argparse
import hashlib
import json

from training.utils import PROJECT_ROOT, git_commit


LOCKED_FILES = (
    "configs/qam_aware_v2.yaml",
    "configs/qam_aware_v2_smoke.yaml",
    "models/qam_aware_rfnet.py",
    "training/qam_aware_utils.py",
    "training/train_qam_aware.py",
    "evaluation/evaluate_qam_aware.py",
    "evaluation/evaluate_qam_formal.py",
    "evaluation/compare_qam_v2.py",
    "evaluation/final_blind_audit.py",
    "evaluation/qam_feature_diagnostic.py",
    "scripts/export_qam_aware_onnx.py",
    "tests/test_qam_aware_rfnet.py",
    "tests/test_final_blind_test.py",
    # Reused post-Baseline dependencies are included so the full V2 behavior
    # is protected even though these files predate this experiment.
    "models/dual_domain_rfnet.py",
    "training/resumable_trainer.py",
    "training/ablation_utils.py",
    "datasets/synthetic_dataset.py",
    "configs/baseline_v1_lock.json",
)


def digest(relative: str) -> str:
    return hashlib.sha256((PROJECT_ROOT / relative).read_bytes()).hexdigest()


def current_hashes() -> dict[str, str]:
    return {relative: digest(relative) for relative in LOCKED_FILES}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    path = PROJECT_ROOT / "configs" / "qam_aware_v2_source_lock.json"
    if args.verify:
        recorded = json.loads(path.read_text(encoding="utf-8"))["sha256"]
        changed = {
            relative: {"expected": recorded.get(relative), "actual": actual}
            for relative, actual in current_hashes().items()
            if recorded.get(relative) != actual
        }
        if changed:
            raise SystemExit("QAM-Aware V2 source lock mismatch:\n" + json.dumps(changed, indent=2))
        print(f"Verified {len(recorded)} QAM-Aware V2 source/config files.")
        return
    manifest = {
        "name": "QAM-Aware RFNet V2 formal source freeze",
        "policy": "No source, model structure, formal config, or frozen dependency changes after formal training starts.",
        "pre_freeze_parent_git_head": git_commit(),
        "sha256": current_hashes(),
    }
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote {path} with {len(LOCKED_FILES)} SHA-256 entries.")


if __name__ == "__main__":
    main()
