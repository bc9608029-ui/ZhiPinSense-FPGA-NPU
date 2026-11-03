"""Verify integrity of the twelve-class formal records (fail closed).

PROVISIONAL tool.  Checks the invariants that make the formal results auditable:
frozen class order, release-input hash presence, the two-seed contract, the six
OOD domains, per-seed validation/OOD checkpoint pairing, and that no evaluation
touched public test or final blind.  Exits non-zero on the first violation.

Usage:
    python scripts/verify_paired_records.py \
        --acceptance outputs/ad_amr_v1_1_data_v3_12class/formal/acceptance.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

# Must equal datasets.modulation_generator.V1_1_12_MODULATIONS (frozen contract).
FROZEN_12_CLASSES = (
    "OOK", "4ASK", "AM-DSB", "WBFM", "2FSK", "GFSK", "BPSK", "QPSK",
    "8PSK", "16QAM", "64QAM", "OFDM",
)
EXPECTED_SEEDS = (2026, 2027)
EXPECTED_OOD_DOMAINS = (
    "cfo_strong", "phase_noise", "iq_imbalance", "multipath", "clipping", "multi_impairment",
)


def _fail(message: str) -> None:
    raise SystemExit(f"VERIFY FAIL: {message}")


def _check_split_namespace(report: dict, label: str) -> None:
    if report.get("final_blind_test_accessed", False):
        _fail(f"{label} touched final blind test")
    split = str(report.get("split", "")).lower()
    if "validation" not in split or "test" in split or "blind" in split:
        _fail(f"{label} invalid split namespace: {split!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--acceptance",
        default="outputs/ad_amr_v1_1_data_v3_12class/formal/acceptance.json",
    )
    parser.add_argument(
        "--run-root",
        default=None,
        help=(
            "Run-project root against which relative checkpoint paths resolve. "
            "Defaults to the directory that owns the outputs/ tree (three levels "
            "above acceptance.json), so the tool works regardless of the calling cwd."
        ),
    )
    args = parser.parse_args()

    path = Path(args.acceptance)
    if not path.is_file():
        _fail(f"acceptance.json not found: {path}")

    run_root = Path(args.run_root).resolve() if args.run_root else path.resolve().parents[3]

    acceptance = json.loads(path.read_text(encoding="utf-8"))

    classes = list(acceptance.get("class_contract", []))
    if tuple(classes) != FROZEN_12_CLASSES:
        _fail(f"class_contract mismatch: {classes} != {FROZEN_12_CLASSES}")

    if not acceptance.get("release_input_hash"):
        _fail("release_input_hash missing or empty")

    records = acceptance.get("records", [])
    seeds = [record.get("seed") for record in records]
    if len(records) != 2 or tuple(seeds) != EXPECTED_SEEDS:
        _fail(f"seed contract mismatch: {seeds} != {EXPECTED_SEEDS}")

    for record in records:
        seed = record.get("seed")
        for section in ("validation", "fake_int8"):
            _check_split_namespace(record.get(section) or {}, f"seed={seed} {section}")

        ood = record.get("ood", {})
        missing = [d for d in EXPECTED_OOD_DOMAINS if d not in ood]
        if missing:
            _fail(f"seed={seed} missing OOD domains: {missing}")

        base_checkpoint = (record.get("validation") or {}).get("checkpoint")
        for domain in EXPECTED_OOD_DOMAINS:
            report = ood[domain] or {}
            _check_split_namespace(report, f"seed={seed} ood {domain}")
            if report.get("checkpoint") != base_checkpoint:
                _fail(f"seed={seed} ood {domain} checkpoint differs from validation")

        ckpt = record.get("checkpoint")
        if ckpt:
            ckpt_path = Path(ckpt)
            if not ckpt_path.is_absolute():
                ckpt_path = run_root / ckpt_path
            if not ckpt_path.is_file():
                _fail(f"seed={seed} checkpoint file missing: {ckpt} (run_root={run_root})")

    print(
        "VERIFY OK: class order, 2-seed contract, 6 OOD domains, checkpoint pairing, "
        f"no test/blind access (source={path})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
