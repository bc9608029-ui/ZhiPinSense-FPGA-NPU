#!/usr/bin/env python3
"""Score FIXED/BAND_SCAN board output with a fixed, no-omission denominator."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def indexed(records: list[dict], name: str) -> dict[int, dict]:
    result: dict[int, dict] = {}
    for row in records:
        seq = int(row["seq"])
        if seq in result:
            raise ValueError(f"duplicate seq {seq} in {name}")
        result[seq] = row
    return result


def score(results: dict, truth: dict, expected_center_hz: int | None = None) -> dict:
    truth_rows = indexed(list(truth.get("records", [])), "truth")
    board_rows = indexed(list(results.get("records", [])), "results")
    expected_n = int(truth.get("n", len(truth_rows)))
    if expected_n != len(truth_rows):
        raise ValueError("truth n disagrees with truth records")

    confusion = [[0 for _ in range(24)] for _ in range(24)]
    per_class = [{"total": 0, "correct": 0} for _ in range(24)]
    correct = 0
    missing = 0
    invalid = 0
    full_sweeps = 0
    locked_checks = 0
    hit_errors = []
    mode_counts: dict[str, int] = {}
    for seq, expected in truth_rows.items():
        label = int(expected["class_index"])
        per_class[label]["total"] += 1
        row = board_rows.get(seq)
        pred = -1
        if row is None:
            missing += 1
        else:
            mode = str(row.get("mode", "UNKNOWN"))
            mode_counts[mode] = mode_counts.get(mode, 0) + 1
            arm = row.get("candidate", {})
            pred = int(arm.get("pred", -1)) if arm.get("finite") else -1
            if not 0 <= pred < 24:
                invalid += 1
                pred = -1
            steps = list(row.get("scan_steps", []))
            if len(steps) > 1:
                full_sweeps += 1
            if len(steps) == 1 and bool(steps[0].get("locked_check")):
                locked_checks += 1
            if expected_center_hz is not None and "scan_hit" in row:
                hit_errors.append(float(row["scan_hit"]["signal_hz"]) - expected_center_hz)
        if pred >= 0:
            confusion[label][pred] += 1
        if pred == label:
            correct += 1
            per_class[label]["correct"] += 1

    extras = sorted(set(board_rows) - set(truth_rows))
    if extras:
        raise ValueError(f"unexpected result seq values: {extras[:5]}")
    for item in per_class:
        item["accuracy"] = item["correct"] / item["total"] if item["total"] else None
    return {
        "kind": "RML24_DUALMODE_SCORE_V1",
        "denominator": expected_n,
        "correct": correct,
        "accuracy": correct / expected_n if expected_n else 0.0,
        "missing": missing,
        "invalid": invalid,
        "mode_counts": mode_counts,
        "full_sweeps": full_sweeps,
        "locked_checks": locked_checks,
        "expected_center_hz": expected_center_hz,
        "frequency_error_hz": hit_errors,
        "max_abs_frequency_error_hz": max((abs(v) for v in hit_errors), default=None),
        "per_class": per_class,
        "confusion_matrix": confusion,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--truth", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--expected-center-hz", type=int)
    args = parser.parse_args()
    report = score(
        json.loads(args.results.read_text(encoding="utf-8")),
        json.loads(args.truth.read_text(encoding="utf-8")),
        args.expected_center_hz,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        f"DUALMODE_SCORE correct={report['correct']}/{report['denominator']} "
        f"accuracy={report['accuracy']:.6f} missing={report['missing']} invalid={report['invalid']} "
        f"full_sweeps={report['full_sweeps']} locked_checks={report['locked_checks']}",
        flush=True,
    )
    return 0 if report["missing"] == 0 and report["invalid"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

